from __future__ import annotations

import asyncio
import errno
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from rich.text import Text

from stui import cli
from stui._terminal_text import visible_terminal_text
from stui.app import StuiApp, StuiPathInput
from stui.elements import ErrorElement
from stui.path_input import _normalize_path, _normalize_root
from stui.runtime import ApiUsageError, Runtime

PATH_ERROR = "st.path_input paths must not contain surrogate characters."


def test_terminal_text_escapes_surrogates_and_preserves_printable_unicode() -> None:
    surrogates = "".join(chr(value) for value in range(0xD800, 0xE000))
    expected = "".join(
        f"\\x{value - 0xDC00:02x}"
        if 0xDC80 <= value <= 0xDCFF
        else f"\\u{value:04x}"
        for value in range(0xD800, 0xE000)
    )
    printable = "café λ 😀\t\n"

    result = visible_terminal_text(printable + surrogates)

    assert result == printable + expected
    assert result.encode("utf-8", "surrogateescape") == result.encode("utf-8")
    assert visible_terminal_text(result) == result


@pytest.mark.skipif(os.name != "posix", reason="POSIX byte filenames required")
@pytest.mark.parametrize("byte", [0x9B, 0x9C, 0x9D, 0xFF])
def test_byte_filenames_are_safe_in_header_watch_and_inspect(
    tmp_path: Path,
    byte: int,
) -> None:
    name = "app-λ-" + os.fsdecode(bytes([byte])) + ".py"
    script = tmp_path / name
    try:
        script.write_text("import stui as st\nst.write('ready')\n", encoding="utf-8")
    except OSError as exc:
        if exc.errno == errno.EILSEQ:
            pytest.skip("filesystem rejects undecodable byte filenames")
        raise
    assert os.fsencode(script.name) == b"app-\xce\xbb-" + bytes([byte]) + b".py"
    expected = f"app-λ-\\x{byte:02x}.py"
    runtime = Runtime(script)

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True, size=(120, 30)) as pilot:
            await pilot.pause()
            assert app.sub_title == expected
            update = app.screen._compositor.render_update(
                full=True, screen_stack=app.screen_stack,
            )
            assert update is not None
            frame = update.render_segments(app.console)
            assert expected in Text.from_ansi(frame).plain
            frame.encode("utf-8")

            notifications: list[str] = []
            runtime.poll_source_changes = lambda: (script,)
            runtime.prepare_source_reload = lambda paths: None

            async def rerun() -> None:
                return None

            app.action_rerun_script = rerun
            app.notify = lambda message, **kwargs: notifications.append(message)
            await app._poll_script_change()
            assert notifications == [f"Reloaded {expected}"]
            notifications[0].encode("utf-8")

    asyncio.run(scenario())

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONIOENCODING"] = "utf-8:surrogateescape"
    result = subprocess.run(
        [sys.executable, "-m", "stui", "inspect", str(script)],
        capture_output=True, env=env, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert expected.encode("utf-8") in result.stdout
    assert bytes([byte]) not in result.stdout
    assert b"stui inspect passed:" in result.stdout

    result = subprocess.run(
        [sys.executable, "-m", "stui", "inspect", str(script), "--json"],
        capture_output=True, env=env, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["paths"]["script"] == str(script.resolve())


def test_surrogate_filename_display_with_surrogateescape_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = tmp_path / "app.py"
    script.write_text("import stui as st\nst.write('ready')\n", encoding="utf-8")
    report = cli.inspect_script(script)
    runtime = Runtime(script)
    runtime.run_script()
    # Exercise output boundaries even on filesystems that reject byte names.
    display_path = tmp_path / "app-λ-\udc9b\udc9c\udc9d.py"
    expected = "app-λ-\\x9b\\x9c\\x9d.py"
    runtime.script_path = display_path
    monkeypatch.setattr(runtime, "run_script", lambda: runtime.elements)

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            await pilot.pause()
            assert app.sub_title == expected
            runtime.poll_source_changes = lambda: (display_path,)
            runtime.prepare_source_reload = lambda paths: None
            notifications: list[str] = []
            app.notify = lambda message, **kwargs: notifications.append(message)
            await app._poll_script_change()
            assert notifications == [f"Reloaded {expected}"]

    asyncio.run(scenario())

    report["paths"]["script"] = str(display_path)
    report["paths"]["project_root"] = str(display_path.parent / "\udc9d")
    report["paths"]["local_modules"] = [{"name": "\udc9b", "path": str(display_path)}]
    report["paths"]["watch_files"] = [str(display_path)]
    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="utf-8", errors="surrogateescape")
    with monkeypatch.context() as context:
        context.setattr(sys, "stdout", stream)
        cli._print_inspect_report(report)
        stream.flush()
    emitted = output.getvalue()
    assert emitted.count(expected.encode("utf-8")) == 3
    assert all(bytes([byte]) not in emitted for byte in (0x9B, 0x9C, 0x9D))
    assert b"stui inspect passed:" in emitted


@pytest.mark.parametrize("surrogate", ["\ud800", "\udc00", "\udc9b", "\udfff"])
def test_path_normalization_rejects_surrogates_before_changing_file_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surrogate: str,
) -> None:
    unsafe = f"file-{surrogate}"
    for normalize in (
        lambda: _normalize_path(unsafe, root=str(tmp_path)),
        lambda: _normalize_root(unsafe, tmp_path),
        lambda: _normalize_root(Path(unsafe), tmp_path),
        lambda: _normalize_root(None, tmp_path / unsafe),
        lambda: _normalize_path("file.txt", root=str(tmp_path / unsafe)),
        lambda: _normalize_root("relative", tmp_path / unsafe),
    ):
        with pytest.raises(ApiUsageError, match=PATH_ERROR):
            normalize()

    monkeypatch.setenv("HOME", str(tmp_path / "home-\udc9b"))
    with pytest.raises(ApiUsageError, match=PATH_ERROR):
        _normalize_root("~/root", tmp_path)
    with pytest.raises(ApiUsageError, match=PATH_ERROR):
        _normalize_path("~/file.txt", root=str(tmp_path))


def test_path_input_rejects_surrogate_edits_without_committing_or_calling_back(
    tmp_path: Path,
) -> None:
    script = tmp_path / "app.py"
    script.write_text(
        "import stui as st\nfrom stui.path_input import path_input\n"
        "def changed():\n    st.session_state.called = True\n"
        "path_input('Path', 'original.txt', key='path', on_change=changed)\n",
        encoding="utf-8",
    )
    runtime = Runtime(script)
    runtime.run_script()
    original = str(tmp_path / "original.txt")
    # A different, real file must not become the surrogate filename's target.
    (tmp_path / "file-\\x9b.txt").touch()
    runtime.set_widget_value("path", "file-\udc9b.txt")
    runtime.run_script()
    assert runtime.elements == [ErrorElement(PATH_ERROR)]
    assert runtime.session_state["path"] == original
    assert "called" not in runtime.session_state

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            await pilot.pause()
            widget = app.query_one(StuiPathInput)
            notifications: list[str] = []
            widget.notify = lambda message, **kwargs: notifications.append(message)
            widget.replace("file-\udc9b.txt", 0, len(widget.value))
            assert widget.value == original
            assert notifications == [PATH_ERROR]

    asyncio.run(scenario())
