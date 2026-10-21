from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from os import PathLike
from pathlib import Path
from typing import Any, Literal

from ._terminal_text import visible_terminal_text

PathKind = Literal["file", "directory", "any"]
PATH_KINDS: tuple[PathKind, ...] = ("file", "directory", "any")


def _visible_path_text(value: object) -> str:
    return visible_terminal_text(value).replace("\t", "\\x09").replace(
        "\n", "\\x0a"
    )


def _validate_path_text(value: str) -> None:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        from .runtime import ApiUsageError

        raise ApiUsageError(
            "st.path_input paths must not contain surrogate characters."
        )


def _normalize_root(
    root: str | PathLike[str] | None,
    script_directory: Path,
) -> str:
    raw_root = os.fspath(script_directory if root is None else root)
    root_text = os.fsdecode(raw_root)
    _validate_path_text(root_text)
    root_text = _visible_path_text(root_text)
    expanded = os.path.expanduser(root_text)
    if not os.path.isabs(expanded):
        expanded = os.path.join(str(script_directory), expanded)
    normalized = os.path.abspath(expanded)
    _validate_path_text(normalized)
    return normalized


def _normalize_path(value: object, *, root: str) -> str:
    raw_value = str(value)
    _validate_path_text(raw_value)
    raw_value = _visible_path_text(raw_value)
    if raw_value == "":
        return ""
    expanded = os.path.expanduser(raw_value)
    if not os.path.isabs(expanded):
        expanded = os.path.join(root, expanded)
    normalized = os.path.abspath(expanded)
    _validate_path_text(normalized)
    return normalized


def _normalize_extensions(
    extensions: str | Iterable[str] | None,
) -> tuple[str, ...]:
    if extensions is None:
        return ()
    raw_extensions: Iterable[str]
    if isinstance(extensions, str):
        raw_extensions = (extensions,)
    else:
        raw_extensions = extensions

    normalized: list[str] = []
    try:
        for raw_extension in raw_extensions:
            if not isinstance(raw_extension, str):
                raise ValueError
            extension = _visible_path_text(raw_extension).strip()
            if extension.startswith("*."):
                extension = extension[1:]
            elif extension and not extension.startswith("."):
                extension = f".{extension}"
            if extension in {"", "."} or "/" in extension or "\\" in extension:
                raise ValueError
            extension = extension.casefold()
            if extension not in normalized:
                normalized.append(extension)
    except TypeError as exc:
        raise ValueError from exc
    return tuple(normalized)


def _matches_extension(value: str, extensions: tuple[str, ...]) -> bool:
    filename = value.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return any(filename.endswith(extension) for extension in extensions)


def _validation_error(
    value: str,
    *,
    kind: PathKind,
    must_exist: bool,
    extensions: tuple[str, ...],
) -> str | None:
    if value == "":
        return "Path is required." if must_exist else None

    exists = os.path.exists(value)
    if not exists:
        if must_exist:
            return "Path does not exist."
        if kind == "file" and extensions and not _matches_extension(
            value, extensions
        ):
            return _extension_error(extensions)
        return None
    if kind == "file" and not os.path.isfile(value):
        return "Path must be a file."
    if kind == "directory" and not os.path.isdir(value):
        return "Path must be a directory."
    is_file = kind == "file" or (kind == "any" and os.path.isfile(value))
    if is_file and extensions and not _matches_extension(value, extensions):
        return _extension_error(extensions)
    if not os.access(value, os.R_OK):
        return "Path is not readable."
    return None


def _extension_error(extensions: tuple[str, ...]) -> str:
    return f"File extension must be one of: {', '.join(extensions)}."


def path_input(
    label: str,
    value: str = "",
    *,
    root: str | PathLike[str] | None = None,
    kind: PathKind = "any",
    must_exist: bool = False,
    extensions: str | Iterable[str] | None = None,
    browse: bool = True,
    key: str | None = None,
    disabled: bool = False,
    on_change: Callable[..., Any] | None = None,
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> str:
    from .runtime import get_current_runtime

    return get_current_runtime().path_input(
        label,
        value,
        root=root,
        kind=kind,
        must_exist=must_exist,
        extensions=extensions,
        browse=browse,
        key=key,
        disabled=disabled,
        on_change=on_change,
        args=args,
        kwargs=kwargs,
    )
