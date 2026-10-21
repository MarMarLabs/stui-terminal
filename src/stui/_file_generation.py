"""Create CLI output without reopening an attacker-substituted destination."""

from __future__ import annotations

import os
import secrets
import stat
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _Directory:
    path: Path
    fd: int | None

    def entry(self, name: str) -> str | Path:
        return name if self.fd is not None else self.path / name


def _windows_kernel():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    info = kernel.GetFileInformationByHandleEx
    info.argtypes = (
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    )
    info.restype = wintypes.BOOL
    return kernel


def _pin_windows_directory(path: Path, stack: ExitStack) -> _Directory:
    # Python's dir_fd operations are unavailable on Windows. Keep every ancestor
    # open without write/delete sharing instead, including while publishing.
    import ctypes
    from ctypes import wintypes

    kernel = _windows_kernel()
    # OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT.
    # FILE_TRAVERSE participates in sharing checks; metadata-only access does not.
    handle = kernel.CreateFileW(str(path), 0x20, 1, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    stack.callback(kernel.CloseHandle, handle)
    attributes = (wintypes.DWORD * 2)()
    # FileAttributeTagInfo = 9; reject junctions and other reparse points.
    if not kernel.GetFileInformationByHandleEx(
        handle, 9, attributes, ctypes.sizeof(attributes),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if attributes[0] & 0x400 or not attributes[0] & 0x10:
        raise NotADirectoryError(f"not a plain directory: {path}")
    return _Directory(path, None)


def _create_file(directory: _Directory, name: str) -> int:
    if os.name != "nt":
        return os.open(
            directory.entry(name), os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o666, dir_fd=directory.fd,
        )
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = _windows_kernel()
    # GENERIC_WRITE, FILE_SHARE_READ, CREATE_NEW, OPEN_REPARSE_POINT | NORMAL.
    # The CRT's os.open can follow a dangling symlink despite O_EXCL.
    handle = kernel.CreateFileW(
        str(directory.entry(name)), 0x40000000, 1, None, 1, 0x00200080, None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise


def _pin_directory(
    path: Path, stack: ExitStack, parent: _Directory | None = None,
    name: str | None = None,
) -> _Directory:
    if os.name == "nt":
        return _pin_windows_directory(path, stack)
    access = getattr(os, "O_SEARCH", getattr(os, "O_PATH", os.O_RDONLY))
    fd = os.open(
        name if name is not None else path,
        access | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=parent.fd if parent is not None else None,
    )
    stack.callback(os.close, fd)
    return _Directory(path, fd)


def _parent_directory(path: Path, stack: ExitStack) -> _Directory:
    parent_path = path.parent.absolute()
    # macOS supplies these aliases in its root-owned filesystem namespace.
    # Resolve only that OS prefix, never links below an attacker-writable path.
    if sys.platform == "darwin" and parent_path.parts[1:2] in (
        ("tmp",), ("var",), ("etc",),
    ):
        parent_path = Path("/", parent_path.parts[1]).resolve().joinpath(
            *parent_path.parts[2:],
        )
    directory = _pin_directory(Path(parent_path.anchor), stack)
    for part in parent_path.parts[1:]:
        child = directory.path / part
        try:
            directory = _pin_directory(child, stack, directory, part)
        except FileNotFoundError:
            try:
                os.mkdir(directory.entry(part), dir_fd=directory.fd)
            except FileExistsError:
                pass
            directory = _pin_directory(child, stack, directory, part)
    return directory


def write_generated_file(
    path: Path,
    content: str,
    *,
    force: bool,
    directory_filename: str | None = None,
) -> Path:
    """Write a file, or copy an example into a directory, without following it."""
    with ExitStack() as stack:
        directory = _parent_directory(path, stack)
        name = path.name or "."
        try:
            existing = os.stat(
                directory.entry(name), dir_fd=directory.fd, follow_symlinks=False,
            )
        except FileNotFoundError:
            existing = None
        is_directory = existing is not None and stat.S_ISDIR(existing.st_mode)
        if directory_filename is not None and (is_directory or path.suffix == ""):
            if not is_directory:
                os.mkdir(directory.entry(name), dir_fd=directory.fd)
            directory = _pin_directory(directory.path / name, stack, directory, name)
            path = path / directory_filename
            name = directory_filename
            try:
                existing = os.stat(
                    directory.entry(name), dir_fd=directory.fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                existing = None
        elif is_directory:
            raise IsADirectoryError(str(path))

        if existing is not None and stat.S_ISLNK(existing.st_mode):
            try:
                target = os.stat(directory.entry(name), dir_fd=directory.fd)
            except FileNotFoundError:
                pass
            else:
                if stat.S_ISDIR(target.st_mode):
                    raise IsADirectoryError(str(path))

        if not force:
            fd = _create_file(directory, name)
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(content)
        else:
            temporary = f".stui-{secrets.token_hex(16)}.tmp"
            fd = _create_file(directory, temporary)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as output:
                    if (
                        os.name != "nt" and existing is not None
                        and stat.S_ISREG(existing.st_mode)
                    ):
                        os.fchmod(output.fileno(), existing.st_mode & 0o777)
                    output.write(content)
                os.replace(
                    directory.entry(temporary), directory.entry(name),
                    src_dir_fd=directory.fd, dst_dir_fd=directory.fd,
                )
            finally:
                try:
                    os.unlink(directory.entry(temporary), dir_fd=directory.fd)
                except FileNotFoundError:
                    pass
    return path
