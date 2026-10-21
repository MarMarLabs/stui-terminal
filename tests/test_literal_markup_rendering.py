from __future__ import annotations

import asyncio
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console
from rich.text import Text
from textual.command import CommandList
from textual.content import Content
from textual.widgets import Static
from textual.widgets._toast import Toast
from textual.widgets._tooltip import Tooltip

from stui.app import (
    StuiApp,
    StuiButton,
    StuiMultiselect,
    StuiRadioSet,
    StuiSelectbox,
    StuiSlider,
)
from stui.elements import TableElement
from stui.runtime import Runtime

MARKUP = (
    "[link=x]ok[/link]",
    "[@click=app.quit]quit[/]",
    "[bold]loud[/]",
    "[/bold]",
)


def write_script(tmp_path: Path, body: str, payload: str) -> Path:
    script = tmp_path / "app.py"
    script.write_text(
        f"import stui as st\npayload = {payload!r}\n{body}\n",
        encoding="utf-8",
    )
    return script


@pytest.mark.parametrize("payload", MARKUP)
@pytest.mark.parametrize(
    "sink",
    [
        "st.button(payload)",
        "st.checkbox(payload)",
        "st.text_input(payload)",
        "st.text_area(payload)",
        "st.number_input(payload)",
        "st.path_input(payload)",
        "st.toggle(payload)",
        "st.selectbox(payload, ['ordinary'])",
        "st.selectbox('Choice', [payload])",
        "st.radio(payload, ['ordinary'])",
        "st.radio('Choice', [payload])",
        "st.multiselect(payload, ['ordinary'])",
        "st.multiselect('Choices', [payload])",
        "st.slider(payload)",
        "with st.expander(payload):\n    st.text('details')",
        "with st.form('form'):\n    st.form_submit_button(payload)",
        "st.progress(50, text=payload)",
        "st.toast(payload)",
        "st.table({payload: [payload]})",
        "st.dataframe({payload: [payload]})",
    ],
)
def test_plain_public_display_values_remain_literal(
    tmp_path: Path, payload: str, sink: str
) -> None:
    runtime = Runtime(write_script(tmp_path, sink, payload))

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(
            headless=True, size=(120, 40), notifications=True
        ) as pilot:
            await pilot.pause()
            update = app.screen._compositor.render_update(
                full=True, screen_stack=app.screen_stack
            )
            assert update is not None
            frame = update.render_segments(app.console)
            assert payload in Text.from_ansi(frame).plain
            assert "\x1b]8;" not in frame
            for widget in app.query(Static):
                content = widget._render()
                if isinstance(content, Content):
                    assert all(
                        "@click" not in str(span.style)
                        and "link=" not in str(span.style)
                        for span in content.spans
                    )

    asyncio.run(scenario())


@pytest.mark.parametrize("payload", MARKUP)
def test_widget_help_is_literal_in_tooltip_renderer(
    tmp_path: Path, payload: str
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            "st.button('Button', help=payload)\nst.slider('Slider', help=payload)",
            payload,
        )
    )

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            await pilot.pause()
            for widget_type in (StuiButton, StuiSlider):
                widget = app.query_one(widget_type)
                content = Tooltip(widget.tooltip).render()
                assert isinstance(content, Content)
                assert content.plain == payload
                assert not content.spans

    asyncio.run(scenario())


@pytest.mark.parametrize("payload", MARKUP)
def test_static_table_headers_and_cells_are_literal(payload: str) -> None:
    rendered = StuiApp._render_table(
        TableElement(headers=(payload,), rows=((payload,),)), 120
    )
    console = Console(file=StringIO(), width=120, force_terminal=True, record=True)

    segments = list(console.render(rendered))
    console.print(rendered)

    assert console.export_text().count(payload) == 2
    assert all(segment.style is None or not segment.style.link for segment in segments)
    assert "\x1b]8;" not in console.file.getvalue()


@pytest.mark.parametrize("failed", [False, True])
def test_watch_filename_is_literal_in_notification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    payload = "[bold]changed"
    runtime = Runtime(write_script(tmp_path, "st.text('ready')", payload))
    changed = tmp_path / f"{payload}.py"
    monkeypatch.setattr(StuiApp, "set_interval", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, "poll_source_changes", lambda: (changed,))
    monkeypatch.setattr(runtime, "prepare_source_reload", lambda paths: None)

    async def scenario() -> None:
        app = StuiApp(runtime, watch=True)
        async with app.run_test(headless=True, notifications=True) as pilot:
            if failed:
                runtime.script_path.write_text("raise ValueError('boom')\n")
            await app._poll_script_change()
            await pilot.pause()
            content = app.query_one(Toast).render()
            assert changed.name in content.plain
            assert not content.spans
            assert ("Reload failed" in content.plain) is failed

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("api", "widget_type", "key", "expected_value"),
    [
        ("selectbox", StuiSelectbox, "right", "[@click=app.quit]quit[/]"),
        ("radio", StuiRadioSet, "down", "[@click=app.quit]quit[/]"),
        ("multiselect", StuiMultiselect, "down", ("[@click=app.quit]quit[/]",)),
    ],
)
def test_option_updates_preserve_literal_text_and_original_state(
    tmp_path: Path, api: str, widget_type, key: str, expected_value
) -> None:
    payload = "[@click=app.quit]quit[/]"
    runtime = Runtime(
        write_script(
            tmp_path,
            f"st.{api}('Choice', ['ordinary', payload], key='choice')",
            payload,
        )
    )

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            app.set_focus(app.query_one(widget_type))
            await pilot.press(key)
            if api == "multiselect":
                await pilot.press("space")
            await pilot.pause()
            assert runtime.session_state["choice"] == expected_value
            content = app.query_one(widget_type).render()
            assert payload in content.plain
            assert not content.spans

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    (
        *MARKUP,
        "[ @click=app.quit]quit[/]",
        "[ link=x]ok[/]",
        "[BOLD]loud[/]",
        r"\[bold]plain[/]",
        "trailing\\",
        "[bold",
    ),
)
def test_command_palette_titles_remain_literal_when_discovered_and_searched(
    tmp_path: Path, payload: str
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            "st.tabs([payload], key=payload)\n"
            "st.tabs([payload], key='other')\n"
            "st.data_table([1], key='table-' + payload)",
            payload,
        )
    )

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            await pilot.pause()
            commands = [
                command
                for command in app.get_system_commands(app.screen)
                if command.title.startswith(("Switch tab:", "Explore table:"))
            ]
            assert len(commands) == 3
            provider = next(iter(app.COMMANDS))(app.screen)
            discovered = [
                hit
                async for hit in provider.discover()
                if hit.text.startswith(("Switch tab:", "Explore table:"))
            ]
            searched = [hit async for hit in provider.search("tab")]
            assert len(discovered) == len(searched) == 3
            for hit in discovered:
                assert isinstance(hit.prompt, Content)
                assert hit.prompt.plain == hit.text
                assert payload in hit.text
                assert not hit.prompt.spans
            for hit in searched:
                assert hit.prompt.plain == hit.text
                assert payload in hit.text
                assert all(
                    "@click" not in str(span.style) and "link=" not in str(span.style)
                    for span in hit.prompt.spans
                )
            switch = next(
                command
                for command in commands
                if command.title.startswith("Switch tab:")
            )
            await switch.callback()
            assert runtime.session_state[payload] == 0

    asyncio.run(scenario())


def test_palette_search_highlights_original_offsets_after_literal_brackets(
    tmp_path: Path,
) -> None:
    payload = "Page [1] Details"
    runtime = Runtime(write_script(tmp_path, "st.tabs([payload])", payload))

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            await pilot.pause()
            provider = next(iter(app.COMMANDS))(app.screen)
            hits = [hit async for hit in provider.search("Details")]
            assert len(hits) == 1
            hit = hits[0]
            assert hit.text == "Switch tab: Page [1] Details"
            start = hit.text.index("Details")
            assert {
                offset
                for span in hit.prompt.spans
                for offset in range(span.start, span.end)
            } == set(range(start, start + len("Details")))

    asyncio.run(scenario())


def test_mounted_command_palette_has_no_injected_action_or_hyperlink(
    tmp_path: Path,
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            "st.tabs([payload])\nst.data_table([1], key='[ link=x]ok[/]')",
            "[ @click=app.quit]quit[/]",
        )
    )

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True, size=(120, 40)) as pilot:
            await pilot.press("ctrl+p")
            await pilot.pause()
            commands = app.screen.query_one(CommandList)
            prompts = [
                commands.get_option_at_index(index).prompt
                for index in range(commands.option_count)
            ]
            assert any(
                "[ @click=app.quit]quit[/]" in prompt.plain for prompt in prompts
            )
            assert any("[ link=x]ok[/]" in prompt.plain for prompt in prompts)
            assert all(
                "@click" not in str(span.style) and "link=" not in str(span.style)
                for prompt in prompts
                for span in prompt.spans
            )
            update = app.screen._compositor.render_update(
                full=True, screen_stack=app.screen_stack
            )
            assert update is not None
            assert "\x1b]8;" not in update.render_segments(app.console)

    asyncio.run(scenario())


def test_explicit_markdown_keeps_formatting(tmp_path: Path) -> None:
    runtime = Runtime(write_script(tmp_path, "st.markdown('**formatted**')", ""))

    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            await pilot.pause()
            update = app.screen._compositor.render_update(
                full=True, screen_stack=app.screen_stack
            )
            assert update is not None
            frame = update.render_segments(app.console)
            assert "formatted" in Text.from_ansi(frame).plain
            assert "**formatted**" not in Text.from_ansi(frame).plain

    asyncio.run(scenario())
