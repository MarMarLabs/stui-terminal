from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from rich.text import Text

from stui.app import StuiApp, StuiSlider, StuiTextInput
from stui.elements import (
    ErrorElement,
    MultiselectElement,
    SliderElement,
    ToggleElement,
)
from stui.runtime import Runtime

OSC = "\x1b]0;x\x1b\\"
CSI = "\x1b[2J"
C1_CSI = "\x9b0m"
PAYLOAD = f"line\n\t\u03bb{OSC}{CSI}{C1_CSI}END"
LINK_MARKUP = "[link='https://attacker.invalid/phish']trusted.example[/]"
PAYLOAD_SOURCE = (
    r'payload = "line\n\t\u03bb\x1b]0;x'
    r'\x1b\\\x1b[2J\x9b0mEND"'
)


def write_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "app.py"
    script.write_text(
        f"import stui as st\n{PAYLOAD_SOURCE}\n{body}",
        encoding="utf-8",
    )
    return script


async def render_frame(
    runtime: Runtime,
    *,
    notifications: bool = False,
) -> str:
    app = StuiApp(runtime)
    async with app.run_test(
        headless=True,
        size=(120, 40),
        notifications=notifications,
    ) as pilot:
        await pilot.pause()
        update = app.screen._compositor.render_update(
            full=True,
            screen_stack=app.screen_stack,
        )
        assert update is not None
        return update.render_segments(app.console)


def assert_controls_are_visible(frame: str) -> None:
    assert OSC not in frame
    assert CSI not in frame
    assert C1_CSI not in frame
    visible_frame = "".join(Text.from_ansi(frame).plain.split())
    assert "\\x1b]0;x\\x1b\\" in visible_frame
    assert "\\x1b[2J\\x9b0mEND" in visible_frame
    assert "\u03bb" in visible_frame


@pytest.mark.parametrize("sink", ["st.write(payload)", "st.text(payload)"])
def test_plain_text_sinks_do_not_parse_rich_markup(
    tmp_path: Path,
    sink: str,
) -> None:
    script = tmp_path / "app.py"
    script.write_text(
        f"import stui as st\npayload = {LINK_MARKUP!r}\n{sink}\n",
        encoding="utf-8",
    )

    frame = asyncio.run(render_frame(Runtime(script)))

    assert LINK_MARKUP in Text.from_ansi(frame).plain
    assert "\x1b]8;" not in frame


@pytest.mark.parametrize(
    "sink",
    [
        "st.title(payload)",
        "st.header(payload)",
        "st.subheader(payload)",
        "st.write(payload)",
        "st.text(payload)",
        "st.caption(payload)",
        "st.markdown(payload)",
        "st.code(payload)",
        "st.help(payload)",
        "st.success(payload)",
        "st.info(payload)",
        "st.warning(payload)",
        "st.error(payload)",
        (
            "try:\n    raise RuntimeError(payload)\n"
            "except RuntimeError as exc:\n    st.exception(exc)"
        ),
        'st.text_input("Value", value=payload, key="value")',
    ],
)
def test_public_text_sinks_make_controls_visible_in_headless_frames(
    tmp_path: Path,
    sink: str,
) -> None:
    runtime = Runtime(write_script(tmp_path, f"{sink}\n"))

    frame = asyncio.run(render_frame(runtime))

    assert_controls_are_visible(frame)


def test_text_input_initial_value_and_placeholder_are_visible_before_render(
    tmp_path: Path,
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            'st.text_input("Input", value=payload, placeholder=payload, key="input")\n',
        )
    )
    async def scenario() -> None:
        app = StuiApp(runtime)
        async with app.run_test(headless=True) as pilot:
            await pilot.pause()
            text_input = app.query_one(StuiTextInput)

            assert OSC not in text_input.value
            assert CSI not in text_input.value
            assert C1_CSI not in text_input.value
            assert text_input.placeholder == PAYLOAD.replace(
                "\x1b", "\\x1b"
            ).replace("\x9b", "\\x9b")
            assert runtime.session_state["input"] == PAYLOAD

    asyncio.run(scenario())


def test_json_keeps_serialized_controls_literal_in_headless_frame(
    tmp_path: Path,
) -> None:
    runtime = Runtime(write_script(tmp_path, 'st.json({"payload": payload})\n'))

    frame = asyncio.run(render_frame(runtime))

    assert OSC not in frame
    assert CSI not in frame
    assert C1_CSI not in frame
    plain = Text.from_ansi(frame).plain
    assert "\\u001b]0;x\\u001b\\\\" in plain
    assert "\\u001b[2J\\u009b0mEND" in plain


def test_slider_label_and_help_make_controls_visible_before_textual_render(
    tmp_path: Path,
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            'st.slider("Label " + payload, help="Help " + payload, key="level")\n',
        )
    )
    runtime.run_script()
    element = runtime.elements[0]
    assert isinstance(element, SliderElement)
    assert element.label == "Label " + PAYLOAD
    assert element.help == "Help " + PAYLOAD

    slider = StuiApp(runtime)._build_widget(element)

    assert isinstance(slider, StuiSlider)
    assert OSC not in slider.label
    assert CSI not in slider.label
    assert C1_CSI not in slider.label
    assert slider.tooltip.plain == "Help " + PAYLOAD.replace("\x1b", "\\x1b").replace(
        "\x9b", "\\x9b"
    )


def test_watch_notification_makes_malicious_filename_controls_visible(
    tmp_path: Path,
) -> None:
    runtime = Runtime(write_script(tmp_path, "st.write('ready')\n"))
    runtime.run_script()
    changed_path = tmp_path / f"watch-{PAYLOAD}.py"
    changed_path.write_text("VALUE = 1\n", encoding="utf-8")
    notifications: list[tuple[str, str]] = []
    app = StuiApp(runtime, watch=True)

    runtime.poll_source_changes = lambda: (changed_path,)
    runtime.prepare_source_reload = lambda changed_paths: None

    async def rerun() -> None:
        return None

    def notify(message: str, *, severity: str, timeout: int, markup: bool) -> None:
        assert markup is False
        notifications.append((message, severity))

    app.action_rerun_script = rerun
    app.notify = notify

    asyncio.run(app._poll_script_change())

    assert notifications == [
        (
            "Reloaded "
            + changed_path.name.replace("\x1b", "\\x1b").replace("\x9b", "\\x9b"),
            "information",
        )
    ]


def test_toast_controls_are_visible_at_the_compositor_boundary(
    tmp_path: Path,
) -> None:
    runtime = Runtime(write_script(tmp_path, "st.toast(payload)\n"))
    runtime.run_script()
    assert runtime.toasts == [PAYLOAD]

    frame = asyncio.run(render_frame(runtime, notifications=True))

    assert_controls_are_visible(frame)


def test_multiselect_label_and_option_controls_are_visible_at_the_compositor_boundary(
    tmp_path: Path,
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            'st.multiselect("label " + payload, ["option " + payload], key="pick")\n',
        )
    )
    frame = asyncio.run(render_frame(runtime))

    element = runtime.elements[0]
    assert isinstance(element, MultiselectElement)
    assert element.label == "label " + PAYLOAD
    assert element.options == ("option " + PAYLOAD,)
    assert "label " in frame
    assert "option " in frame
    assert frame.count("\\x1b]0;x") >= 2
    assert_controls_are_visible(frame)


def test_toggle_label_controls_are_visible_at_the_compositor_boundary(
    tmp_path: Path,
) -> None:
    runtime = Runtime(
        write_script(tmp_path, 'st.toggle("toggle " + payload, key="mode")\n')
    )
    frame = asyncio.run(render_frame(runtime))

    element = runtime.elements[0]
    assert isinstance(element, ToggleElement)
    assert element.label == "toggle " + PAYLOAD
    assert element.key == "mode"
    assert "toggle " in frame
    assert_controls_are_visible(frame)


def test_duplicate_widget_key_controls_are_visible_at_the_compositor_boundary(
    tmp_path: Path,
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            "st.button('First', key=payload)\nst.button('Second', key=payload)\n",
        )
    )
    frame = asyncio.run(render_frame(runtime))

    element = runtime.elements[0]
    assert isinstance(element, ErrorElement)
    assert PAYLOAD in element.traceback
    assert_controls_are_visible(frame)


def test_duplicate_form_key_controls_are_visible_at_the_compositor_boundary(
    tmp_path: Path,
) -> None:
    runtime = Runtime(
        write_script(
            tmp_path,
            (
                "with st.form(payload):\n"
                "    st.write('first')\n"
                "with st.form(payload):\n"
                "    st.write('second')\n"
            ),
        )
    )
    frame = asyncio.run(render_frame(runtime))

    element = runtime.elements[0]
    assert isinstance(element, ErrorElement)
    assert PAYLOAD in element.traceback
    assert_controls_are_visible(frame)
