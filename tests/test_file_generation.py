import os
import stat
import subprocess

import pytest
from typer.testing import CliRunner

from stui import _file_generation, cli


@pytest.fixture(params=["init", "copy", "copy-directory"])
def generator(request, tmp_path):
    directory = tmp_path / "generated"
    directory.mkdir()
    if request.param == "init":
        destination = directory / "app.py"
        args = ["init", str(destination)]
    else:
        destination = directory / "basic.py"
        target = directory if request.param == "copy-directory" else destination
        args = ["example", "copy", "basic", str(target)]
    return args, destination


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("dangling", [False, True])
def test_generators_do_not_follow_leaf_symlinks(generator, tmp_path, force, dangling):
    args, destination = generator
    victim = tmp_path / "victim.py"
    if not dangling:
        victim.write_text("# keep me\n", encoding="utf-8")
    try:
        destination.symlink_to(victim)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    result = CliRunner().invoke(cli.app, args + (["--force"] if force else []))

    if dangling:
        assert not victim.exists()
    else:
        assert victim.read_text(encoding="utf-8") == "# keep me\n"
    if force:
        assert result.exit_code == 0, result.output
        assert not destination.is_symlink()
        assert "st.title" in destination.read_text(encoding="utf-8")
    else:
        assert result.exit_code != 0
        assert "exists:" in result.output
        assert destination.is_symlink()


def test_generators_force_does_not_modify_hardlink_alias(generator, tmp_path):
    args, destination = generator
    victim = tmp_path / "victim.py"
    victim.write_text("# keep me\n", encoding="utf-8")
    os.link(victim, destination)

    result = CliRunner().invoke(cli.app, args + ["--force"])

    assert result.exit_code == 0, result.output
    assert victim.read_text(encoding="utf-8") == "# keep me\n"
    assert "st.title" in destination.read_text(encoding="utf-8")


@pytest.mark.parametrize("force", [False, True])
def test_generators_leaf_swap_before_commit(generator, tmp_path, monkeypatch, force):
    args, destination = generator
    victim = tmp_path / "victim.py"
    victim.write_text("# keep me\n", encoding="utf-8")
    original_create = _file_generation._create_file
    swapped = False

    def swap_before_create(directory, name):
        nonlocal swapped
        if not swapped:
            destination.symlink_to(victim)
            swapped = True
        return original_create(directory, name)

    monkeypatch.setattr(_file_generation, "_create_file", swap_before_create)
    result = CliRunner().invoke(cli.app, args + (["--force"] if force else []))

    assert swapped
    assert victim.read_text(encoding="utf-8") == "# keep me\n"
    assert (result.exit_code == 0) == force, result.output


@pytest.mark.parametrize("force", [False, True])
def test_generators_parent_swap_before_commit(generator, tmp_path, monkeypatch, force):
    args, destination = generator
    directory = destination.parent
    moved = tmp_path / "original-directory"
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    victim = redirected / destination.name
    victim.write_text("# keep me\n", encoding="utf-8")
    original_create = _file_generation._create_file
    attempted = False
    swapped = False

    def swap_before_create(parent, name):
        nonlocal attempted, swapped
        if not attempted:
            attempted = True
            try:
                directory.rename(moved)
            except PermissionError:
                if os.name != "nt":
                    raise
            else:
                directory.symlink_to(redirected, target_is_directory=True)
                swapped = True
        return original_create(parent, name)

    monkeypatch.setattr(_file_generation, "_create_file", swap_before_create)
    result = CliRunner().invoke(cli.app, args + (["--force"] if force else []))

    assert attempted
    assert result.exit_code == 0, result.output
    assert victim.read_text(encoding="utf-8") == "# keep me\n"
    written = (moved if swapped else directory) / destination.name
    assert "st.title" in written.read_text(encoding="utf-8")


@pytest.mark.skipif(os.name == "nt", reason="POSIX descriptor traversal")
@pytest.mark.parametrize("force", [False, True])
def test_generators_reject_parent_swap_during_traversal(
    generator, tmp_path, monkeypatch, force,
):
    args, destination = generator
    directory = destination.parent
    moved = tmp_path / "original-directory"
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    victim = redirected / destination.name
    victim.write_text("# keep me\n", encoding="utf-8")
    original_open = os.open
    swapped = False

    def swap_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == directory.name and flags & os.O_DIRECTORY and not swapped:
            directory.rename(moved)
            directory.symlink_to(redirected, target_is_directory=True)
            swapped = True
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_before_open)
    result = CliRunner().invoke(cli.app, args + (["--force"] if force else []))

    assert swapped
    assert result.exit_code != 0
    assert victim.read_text(encoding="utf-8") == "# keep me\n"
    assert not (moved / destination.name).exists()


def test_force_failure_preserves_destination_and_cleans_temporary_file(
    generator, monkeypatch,
):
    args, destination = generator
    destination.write_text("# keep me\n", encoding="utf-8")

    def fail_replace(*args, **kwargs):
        raise PermissionError("replacement denied")

    monkeypatch.setattr(os, "replace", fail_replace)
    result = CliRunner().invoke(cli.app, args + ["--force"])

    assert result.exit_code != 0
    assert destination.read_text(encoding="utf-8") == "# keep me\n"
    assert list(destination.parent.iterdir()) == [destination]


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_force_preserves_existing_permission_bits(generator):
    args, destination = generator
    destination.write_text("# replace me\n", encoding="utf-8")
    destination.chmod(0o751)

    result = CliRunner().invoke(cli.app, args + ["--force"])

    assert result.exit_code == 0, result.output
    assert stat.S_IMODE(destination.stat().st_mode) == 0o751


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory permissions")
@pytest.mark.parametrize("force", [False, True])
def test_generators_accept_write_search_only_parent(generator, force):
    args, destination = generator
    if args[-1] == str(destination.parent):
        pytest.skip("Typer already requires readable directory arguments")
    if force:
        destination.write_text("# replace me\n", encoding="utf-8")
    destination.parent.chmod(0o300)
    try:
        result = CliRunner().invoke(cli.app, args + (["--force"] if force else []))
    finally:
        destination.parent.chmod(0o700)

    assert result.exit_code == 0, result.output
    assert "st.title" in destination.read_text(encoding="utf-8")


@pytest.mark.parametrize("force", [False, True])
def test_generators_reject_symlinked_parent(generator, tmp_path, force):
    args, destination = generator
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(destination.parent, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")
    destination.write_text("# keep me\n", encoding="utf-8")
    args = args[:-1] + [str(alias / destination.name)]

    result = CliRunner().invoke(cli.app, args + (["--force"] if force else []))

    assert result.exit_code != 0
    assert destination.read_text(encoding="utf-8") == "# keep me\n"


@pytest.mark.parametrize("directory_name", [".", "..", "nested", "dotted.py"])
def test_copy_directory_path_forms(tmp_path, monkeypatch, directory_name):
    working = tmp_path / "working"
    working.mkdir()
    monkeypatch.chdir(working)
    if directory_name == "dotted.py":
        (working / directory_name).mkdir()

    result = CliRunner().invoke(cli.app, ["example", "copy", "basic", directory_name])

    assert result.exit_code == 0, result.output
    assert "st.title" in (working / directory_name / "basic.py").read_text(
        encoding="utf-8",
    )


@pytest.mark.parametrize("name", ["directory", "directory.py"])
@pytest.mark.parametrize("force", [False, True])
def test_copy_does_not_follow_directory_symlink(tmp_path, name, force):
    directory = tmp_path / "victim"
    directory.mkdir()
    victim = directory / "basic.py"
    victim.write_text("# keep me\n", encoding="utf-8")
    destination = tmp_path / name
    try:
        destination.symlink_to(directory, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    result = CliRunner().invoke(
        cli.app,
        ["example", "copy", "basic", str(destination)] + (["--force"] if force else []),
    )

    assert victim.read_text(encoding="utf-8") == "# keep me\n"
    assert result.exit_code != 0
    assert destination.is_symlink()


@pytest.mark.skipif(os.name != "nt", reason="Windows directory handle sharing")
def test_windows_ancestors_cannot_be_opened_for_reparse_writes(
    generator, monkeypatch,
):
    import ctypes
    from ctypes import wintypes

    args, destination = generator
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    create.restype = wintypes.HANDLE
    original_create = _file_generation._create_file
    attempted = False

    def try_write_handles(directory, name):
        nonlocal attempted
        if not attempted:
            attempted = True
            for ancestor in (destination.parent, destination.parent.parent):
                # GENERIC_WRITE, all sharing, OPEN_EXISTING, BACKUP_SEMANTICS.
                handle = create(str(ancestor), 0x40000000, 7, None, 3, 0x02000000, None)
                assert handle == wintypes.HANDLE(-1).value
                assert ctypes.get_last_error() == 32  # ERROR_SHARING_VIOLATION
        return original_create(directory, name)

    monkeypatch.setattr(_file_generation, "_create_file", try_write_handles)
    result = CliRunner().invoke(cli.app, args + ["--force"])

    assert attempted
    assert result.exit_code == 0, result.output
    assert "st.title" in destination.read_text(encoding="utf-8")


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junctions")
@pytest.mark.parametrize("force", [False, True])
def test_generators_reject_junction_parent(generator, tmp_path, force):
    args, destination = generator
    junction = tmp_path / "junction"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(destination.parent)],
        check=True, capture_output=True, text=True,
    )
    try:
        destination.write_text("# keep me\n", encoding="utf-8")
        args = args[:-1] + [str(junction / destination.name)]

        result = CliRunner().invoke(cli.app, args + (["--force"] if force else []))

        assert result.exit_code != 0
        assert destination.read_text(encoding="utf-8") == "# keep me\n"
    finally:
        junction.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse-point mutation")
def test_windows_publish_cannot_be_redirected_by_in_place_junction(
    generator, tmp_path, monkeypatch,
):
    import ctypes
    import struct
    from ctypes import wintypes

    args, destination = generator
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    victim = redirected / destination.name
    victim.write_text("# keep me\n", encoding="utf-8")
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
    control = kernel.DeviceIoControl
    control.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    control.restype = wintypes.BOOL
    substitute = ("\\??\\" + str(redirected)).encode("utf-16-le")
    printed = str(redirected).encode("utf-16-le")
    names = substitute + b"\0\0" + printed + b"\0\0"
    payload = struct.pack(
        "<IHHHHHH", 0xA0000003, 8 + len(names), 0,
        0, len(substitute), len(substitute) + 2, len(printed),
    ) + names

    def make_junction(path):
        handle = create(str(path), 0x40000000, 7, None, 3, 0x02200000, None)
        assert handle != wintypes.HANDLE(-1).value
        try:
            buffer = ctypes.create_string_buffer(payload)
            returned = wintypes.DWORD()
            succeeded = control(
                handle, 0x900A4, buffer, len(payload),
                None, 0, ctypes.byref(returned), None,
            )
            return bool(succeeded), ctypes.get_last_error()
        finally:
            close(handle)

    empty_control = tmp_path / "empty-control"
    empty_control.mkdir()
    assert make_junction(empty_control)[0]
    empty_control.rmdir()
    attempted = False

    def attack_publish(source, target, **kwargs):
        nonlocal attempted
        attempted = True
        os.unlink(source)
        guards = list(destination.parent.glob("*.guard"))
        assert len(guards) == 1
        with pytest.raises(PermissionError):
            guards[0].unlink()
        assert make_junction(destination.parent) == (False, 145)
        raise FileNotFoundError("attacker removed the staging entry")

    monkeypatch.setattr(os, "replace", attack_publish)
    result = CliRunner().invoke(cli.app, args + ["--force"])

    assert attempted
    assert isinstance(result.exception, FileNotFoundError)
    assert victim.read_text(encoding="utf-8") == "# keep me\n"
    assert not list(destination.parent.iterdir())
