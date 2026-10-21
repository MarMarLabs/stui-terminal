from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Iterable
from functools import partial
from pathlib import Path

from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table as RichTable
from rich.text import Text
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    ProgressBar,
    Static,
    Switch,
    Tab,
    Tabs,
    TextArea,
)

from ._terminal_text import visible_terminal_text
from .cache import cache_data, cache_resource
from .diagnostics import runtime_snapshot
from .elements import (
    AlertElement,
    BarChartElement,
    ButtonElement,
    CaptionElement,
    CheckboxElement,
    CodeElement,
    ColumnsElement,
    ContainerElement,
    DataTableElement,
    DividerElement,
    ErrorElement,
    ExceptionElement,
    ExpanderElement,
    HeaderElement,
    HelpElement,
    JsonElement,
    LineChartElement,
    MarkdownElement,
    MetricElement,
    MultiselectElement,
    NumberInputElement,
    PathInputElement,
    ProgressElement,
    RadioElement,
    SelectboxElement,
    SliderElement,
    SpinnerElement,
    StatusElement,
    SubheaderElement,
    TableElement,
    TabsElement,
    TextAreaElement,
    TextElement,
    TextInputElement,
    TitleElement,
    ToggleElement,
    WriteElement,
)
from .path_input import _validate_path_text, _visible_path_text
from .runtime import ApiUsageError, Runtime
from .widgets.data_explorer import DataExplorerScreen
from .widgets.data_table import StuiDataTable
from .widgets.slider import StuiSlider

SUPPORTED_THEMES = {"default", "high-contrast"}
HIGH_CONTRAST_CLASS = "stui-high-contrast"
MAX_WIDGET_LABEL_WIDTH = 72
MAX_STATIC_LABEL_WIDTH = 120
MAX_TABLE_COLUMNS = 8
MIN_TABLE_COLUMN_WIDTH = 6
MAX_TABLE_COLUMN_WIDTH = 24
MIN_RENDERED_COLUMN_WIDTH = 28

HIGH_CONTRAST_CSS = """
    .stui-high-contrast Screen,
    .stui-high-contrast CommandPalette {
        background: #000000;
        color: #ffffff;
    }

    .stui-high-contrast Header,
    .stui-high-contrast Footer {
        background: #000000;
        color: #ffffff;
    }

    .stui-high-contrast .title,
    .stui-high-contrast .header,
    .stui-high-contrast .subheader {
        color: #ffff00;
    }

    .stui-high-contrast .caption,
    .stui-high-contrast .stui-field-label,
    .stui-high-contrast .stui-progress-label {
        color: #ffffff;
    }

    .stui-high-contrast .divider {
        color: #ffffff;
    }

    .stui-high-contrast Button {
        border: tall #ffffff;
    }

    .stui-high-contrast Button:focus {
        background: #ffff00;
        color: #000000;
        text-style: bold;
    }

    .stui-high-contrast Input:focus,
    .stui-high-contrast TextArea:focus,
    .stui-high-contrast .stui-selectbox:focus,
    .stui-high-contrast .stui-radio:focus,
    .stui-high-contrast .stui-multiselect:focus,
    .stui-high-contrast Switch:focus {
        border: tall #ffff00;
        background: #000000;
        color: #ffffff;
    }

    .stui-high-contrast Checkbox:focus,
    .stui-high-contrast .stui-slider:focus {
        border: tall #ffff00;
        background: #000000;
        color: #ffffff;
        text-style: bold;
    }

    .stui-high-contrast .stui-toggle-label {
        color: #ffffff;
    }

    .stui-high-contrast .stui-slider {
        border: tall #ffffff;
        background: #000000;
    }

    .stui-high-contrast .stui-expander:focus {
        border: tall #ffff00;
        background: #000000;
        color: #ffffff;
        text-style: bold;
    }

    .stui-high-contrast .alert-success,
    .stui-high-contrast .alert-info,
    .stui-high-contrast .alert-warning,
    .stui-high-contrast .alert-error,
    .stui-high-contrast .stui-path-error,
    .stui-high-contrast .traceback {
        color: #ffffff;
    }

    .stui-high-contrast .disabled {
        color: #bfbfbf;
    }
"""


def resolve_theme(value: str | None = None) -> str:
    raw_theme = value if value is not None else os.environ.get("STUI_THEME", "")
    theme = raw_theme.strip().lower()
    if theme in SUPPORTED_THEMES:
        return theme
    return "default"


def css_for_theme(base_css: str, theme: str | None = None) -> str:
    if resolve_theme(theme) == "high-contrast":
        return f"{base_css}\n{HIGH_CONTRAST_CSS}"
    return base_css


def dom_id_for_key(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"stui-{digest}"


def script_signature(path: Path) -> tuple[int, int] | None:
    """Cheap change signature for watch mode; None while the file is missing."""
    try:
        stat_result = os.stat(path)
    except OSError:
        return None
    return (stat_result.st_mtime_ns, stat_result.st_size)


def _clip_text(value: object, width: int) -> str:
    text = visible_terminal_text(value)
    if width < 1:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return "." * width
    return f"{text[: width - 3]}..."


def _tab_label(value: object) -> str:
    return _clip_text(
        visible_terminal_text(value).replace("\t", "\\t").replace("\n", "\\n"),
        MAX_WIDGET_LABEL_WIDTH,
    )


def _tab_id(key: str, index: int) -> str:
    return f"{dom_id_for_key(key)}-tab-{index}"


class StuiButton(Button):
    BINDINGS = [
        Binding("enter", "press", "Press button", show=False),
        Binding("space", "press", "Press button", show=False),
    ]

    def __init__(self, element: ButtonElement) -> None:
        self.stui_key = element.key
        super().__init__(
            _clip_text(element.label, MAX_WIDGET_LABEL_WIDTH),
            id=dom_id_for_key(element.key),
            disabled=element.disabled,
            tooltip=(
                visible_terminal_text(element.help)
                if element.help is not None
                else "Enter or Space activates. Tab and Shift+Tab move focus."
            ),
        )


class StuiTextInput(Input):
    def __init__(self, element: TextInputElement) -> None:
        self.stui_key = element.key
        super().__init__(
            value=visible_terminal_text(element.value),
            placeholder=(
                visible_terminal_text(element.placeholder)
                if element.placeholder is not None
                else ""
            ),
            id=dom_id_for_key(element.key),
            disabled=element.disabled,
        )


class StuiPathInput(Input):
    def __init__(self, element: PathInputElement) -> None:
        self.stui_key = element.key
        super().__init__(
            value=_visible_path_text(element.value),
            id=dom_id_for_key(element.key),
            disabled=element.disabled,
        )

    def replace(self, text: str, start: int, end: int) -> None:
        try:
            _validate_path_text(text)
        except ApiUsageError as exc:
            self.notify(str(exc), severity="error")
            return
        super().replace(_visible_path_text(text), start, end)


class StuiTextArea(TextArea):
    BINDINGS = [
        *TextArea.BINDINGS,
        Binding("ctrl+enter", "submit", "Apply text", show=False),
    ]

    class Submitted(Message):
        def __init__(self, text_area: StuiTextArea, value: str) -> None:
            super().__init__()
            self.text_area = text_area
            self.value = value

        @property
        def control(self) -> StuiTextArea:
            return self.text_area

    def __init__(self, element: TextAreaElement) -> None:
        self.stui_key = element.key
        self.stui_max_chars = element.max_chars
        super().__init__(
            text=visible_terminal_text(element.value),
            soft_wrap=True,
            tab_behavior="focus",
            read_only=element.disabled,
            placeholder=(
                visible_terminal_text(element.placeholder)
                if element.placeholder is not None
                else ""
            ),
            id=dom_id_for_key(element.key),
            disabled=element.disabled,
            compact=True,
            highlight_cursor_line=True,
        )
        self.styles.height = element.height

    def replace(
        self,
        insert: str,
        start,
        end,
        *,
        maintain_selection_offset: bool = True,
    ):
        insert = visible_terminal_text(insert)
        if self.stui_max_chars is not None:
            replaced_length = len(self.get_text_range(start, end))
            available = self.stui_max_chars - (len(self.text) - replaced_length)
            insert = insert[: max(0, available)]
        return super().replace(
            insert,
            start,
            end,
            maintain_selection_offset=maintain_selection_offset,
        )

    def action_submit(self) -> None:
        if self.disabled or self.read_only:
            return
        self.post_message(self.Submitted(self, self.text))


class StuiNumberInput(Input):
    def __init__(self, element: NumberInputElement) -> None:
        self.stui_key = element.key
        self.stui_fallback = element.value
        self.stui_min_value = element.min_value
        self.stui_max_value = element.max_value
        self.stui_step = element.step
        super().__init__(
            value=str(element.value),
            id=dom_id_for_key(element.key),
            disabled=element.disabled,
        )


class StuiCheckbox(Checkbox):
    def __init__(self, element: CheckboxElement) -> None:
        self.stui_key = element.key
        super().__init__(
            _clip_text(element.label, MAX_WIDGET_LABEL_WIDTH),
            value=element.value,
            id=dom_id_for_key(element.key),
            disabled=element.disabled,
        )


class StuiSelectbox(Static, can_focus=True):
    BINDINGS = [
        Binding("enter", "choose_next", "Next choice", show=False),
        Binding("right", "choose_next", "Next choice"),
        Binding("down", "choose_next", "Next choice", show=False),
        Binding("left", "choose_previous", "Previous choice"),
        Binding("up", "choose_previous", "Previous choice", show=False),
    ]

    class Changed(Message):
        def __init__(self, selectbox: StuiSelectbox, value: object) -> None:
            super().__init__()
            self.selectbox = selectbox
            self.value = value

    def __init__(self, element: SelectboxElement) -> None:
        self.stui_key = element.key
        self.stui_options = element.options
        self.stui_index = element.index
        super().__init__(
            self._render_value(),
            id=dom_id_for_key(element.key),
            classes="stui-selectbox",
        )
        self.disabled = element.disabled

    def action_choose_next(self) -> None:
        self._move(1)

    def action_choose_previous(self) -> None:
        self._move(-1)

    def _move(self, delta: int) -> None:
        if self.disabled or len(self.stui_options) < 2:
            return
        self.stui_index = (self.stui_index + delta) % len(self.stui_options)
        value = self.stui_options[self.stui_index]
        self.update(self._render_value())
        self.post_message(self.Changed(self, value))

    def _render_value(self) -> str:
        value = self.stui_options[self.stui_index]
        return f"[ {_clip_text(value, MAX_WIDGET_LABEL_WIDTH)} ]"


class StuiRadioSet(Static, can_focus=True):
    BINDINGS = [
        Binding("down", "next_button", "Next option"),
        Binding("right", "next_button", "Next option", show=False),
        Binding("up", "previous_button", "Previous option"),
        Binding("left", "previous_button", "Previous option", show=False),
        Binding("enter", "next_button", "Next option", show=False),
        Binding("space", "next_button", "Next option", show=False),
    ]

    class Changed(Message):
        def __init__(self, radio: StuiRadioSet, value: object) -> None:
            super().__init__()
            self.radio = radio
            self.value = value

    def __init__(self, element: RadioElement) -> None:
        self.stui_key = element.key
        self.stui_options = element.options
        self.stui_index = element.index
        super().__init__(
            self._render_value(),
            id=dom_id_for_key(element.key),
            classes="stui-radio",
        )
        self.disabled = element.disabled

    def action_next_button(self) -> None:
        self._move(1)

    def action_previous_button(self) -> None:
        self._move(-1)

    def _move(self, delta: int) -> None:
        if self.disabled or len(self.stui_options) < 2:
            return
        self.stui_index = (self.stui_index + delta) % len(self.stui_options)
        value = self.stui_options[self.stui_index]
        self.update(self._render_value())
        self.post_message(self.Changed(self, value))

    def _render_value(self) -> str:
        lines = []
        for index, option in enumerate(self.stui_options):
            marker = "*" if index == self.stui_index else " "
            lines.append(f"({marker}) {_clip_text(option, MAX_WIDGET_LABEL_WIDTH)}")
        return "\n".join(lines)


class StuiToggle(Switch):
    def __init__(self, element: ToggleElement) -> None:
        self.stui_key = element.key
        super().__init__(
            value=element.value,
            id=dom_id_for_key(element.key),
            disabled=element.disabled,
        )


class StuiMultiselect(Static, can_focus=True):
    BINDINGS = [
        Binding("down", "cursor_next", "Next option"),
        Binding("right", "cursor_next", "Next option", show=False),
        Binding("up", "cursor_previous", "Previous option"),
        Binding("left", "cursor_previous", "Previous option", show=False),
        Binding("space", "toggle_option", "Toggle option"),
        Binding("enter", "toggle_option", "Toggle option", show=False),
    ]

    class Changed(Message):
        def __init__(
            self,
            multiselect: StuiMultiselect,
            value: tuple[object, ...],
        ) -> None:
            super().__init__()
            self.multiselect = multiselect
            self.value = value

    def __init__(self, element: MultiselectElement, cursor: int = 0) -> None:
        self.stui_key = element.key
        self.stui_options = element.options
        self.stui_selected_indexes = {
            index
            for index, option in enumerate(element.options)
            if option in element.selected
        }
        max_cursor = max(0, len(element.options) - 1)
        self.stui_cursor = min(max(0, cursor), max_cursor)
        super().__init__(
            self._render_value(),
            id=dom_id_for_key(element.key),
            classes="stui-multiselect",
        )
        self.disabled = element.disabled

    def action_cursor_next(self) -> None:
        self._move_cursor(1)

    def action_cursor_previous(self) -> None:
        self._move_cursor(-1)

    def action_toggle_option(self) -> None:
        if self.disabled or not self.stui_options:
            return
        if self.stui_cursor in self.stui_selected_indexes:
            self.stui_selected_indexes.remove(self.stui_cursor)
        else:
            self.stui_selected_indexes.add(self.stui_cursor)
        self.update(self._render_value())
        value = tuple(
            option
            for index, option in enumerate(self.stui_options)
            if index in self.stui_selected_indexes
        )
        self.post_message(self.Changed(self, value))

    def _move_cursor(self, delta: int) -> None:
        if self.disabled or len(self.stui_options) < 2:
            return
        self.stui_cursor = (self.stui_cursor + delta) % len(self.stui_options)
        self.update(self._render_value())

    def _render_value(self) -> str:
        if not self.stui_options:
            return "(no options)"
        lines = []
        for index, option in enumerate(self.stui_options):
            cursor = ">" if index == self.stui_cursor else " "
            marker = "x" if index in self.stui_selected_indexes else " "
            lines.append(
                f"{cursor} [{marker}] {_clip_text(option, MAX_WIDGET_LABEL_WIDTH)}"
            )
        return "\n".join(lines)


class StuiExpander(Vertical, can_focus=True):
    BINDINGS = [
        Binding("enter", "toggle", "Toggle"),
        Binding("space", "toggle", "Toggle", show=False),
    ]

    class Changed(Message):
        def __init__(self, expander: StuiExpander, expanded: bool) -> None:
            super().__init__()
            self.expander = expander
            self.expanded = expanded

    def __init__(
        self,
        element: ExpanderElement,
        *children,
        label_width: int | None = None,
    ) -> None:
        self.stui_key = element.key
        self.stui_expanded = element.expanded
        marker = "-" if element.expanded else "+"
        available_label_width = max(
            8,
            min(MAX_STATIC_LABEL_WIDTH, (label_width or MAX_STATIC_LABEL_WIDTH) - 4),
        )
        label = Static(
            f"[{marker}] {_clip_text(element.label, available_label_width)}",
            classes="stui-expander-label",
        )
        super().__init__(
            label,
            *children,
            id=dom_id_for_key(element.key),
            classes="stui-expander",
        )
        self.tooltip = "Enter or Space toggles. Tab and Shift+Tab move focus."

    def action_toggle(self) -> None:
        self.stui_expanded = not self.stui_expanded
        self.post_message(self.Changed(self, self.stui_expanded))


class StuiApp(App[None]):
    TITLE = "stui"
    CSS = """
    Screen {
        background: #101014;
        color: #e8e8ee;
    }

    Header, Footer {
        background: #15151d;
    }

    #body {
        padding: 1 1;
    }

    .title {
        color: #8ab4ff;
        text-style: bold;
        margin: 0 0 1 0;
    }

    .header {
        color: #d7ddff;
        text-style: bold;
        margin: 1 0 1 0;
    }

    .subheader {
        color: #cfd6ff;
        text-style: bold;
        margin: 1 0 1 0;
    }

    .caption {
        color: #a2a4b3;
        text-style: italic;
        margin: 0 0 1 0;
    }

    .write, .text, .markdown, .code, .json {
        margin: 0 0 1 0;
    }

    .divider {
        color: #343444;
        margin: 1 0;
    }

    .alert {
        margin: 1 0;
    }

    .alert-success {
        color: #d7ffdf;
    }

    .alert-info {
        color: #d8e7ff;
    }

    .alert-warning {
        color: #fff1bd;
    }

    .alert-error {
        color: #ffd9d9;
    }

    Button {
        margin: 1 0;
        min-width: 16;
    }

    Button:focus {
        background: #8ab4ff;
        color: #101014;
        text-style: bold;
    }

    .stui-field {
        margin: 1 0;
    }

    .stui-field-label {
        color: #cfd3df;
    }

    .stui-field-hint {
        color: #8f93a5;
        text-style: italic;
        margin: 0 0 1 0;
    }

    .stui-path-error {
        color: #ffd9d9;
        margin: 0 0 1 0;
    }

    Input, TextArea, Checkbox {
        margin: 0 0 1 0;
    }

    .stui-selectbox, .stui-radio, .stui-multiselect {
        margin: 0 0 1 0;
    }

    Input:focus, TextArea:focus {
        border: tall #8ab4ff;
        background: #202033;
    }

    Checkbox:focus {
        background: #202033;
        color: #ffffff;
        text-style: bold;
    }

    .stui-selectbox:focus, .stui-radio:focus, .stui-multiselect:focus {
        border: tall #8ab4ff;
        background: #202033;
    }

    .stui-toggle {
        height: auto;
        margin: 1 0;
    }

    .stui-toggle-label {
        width: auto;
        padding: 1 0 0 1;
        color: #cfd3df;
    }

    Switch:focus {
        border: tall #8ab4ff;
        background: #202033;
    }

    .stui-slider {
        border: round #343444;
        padding: 1;
        margin: 1 0;
        background: #171722;
    }

    .stui-slider:focus {
        border: round #8ab4ff;
        background: #202033;
        color: #ffffff;
    }

    .disabled {
        color: #777783;
    }

    .error {
        margin: 1 0;
    }

    .traceback {
        color: #ffd7d7;
    }

    .exception {
        margin: 1 0;
    }

    .stui-progress {
        margin: 1 0;
    }

    .stui-progress-label {
        color: #cfd3df;
        margin: 0 0 1 0;
    }

    .stui-status, .stui-spinner, .stui-help {
        margin: 1 0;
    }

    .table {
        margin: 1 0;
    }

    .stui-data-table {
        height: auto;
        margin: 1 0;
    }

    .stui-data-table-widget {
        width: 100%;
    }

    .stui-data-table-summary {
        color: #8f93a5;
        text-style: italic;
    }

    .metric, .bar-chart {
        margin: 1 0;
    }

    .stui-container {
        border-left: solid #343444;
        padding: 0 0 0 1;
        margin: 1 0;
    }

    .stui-columns {
        margin: 1 0;
    }

    .stui-column {
        width: 1fr;
        min-width: 0;
        padding: 0 1 0 0;
    }

    .stui-columns-stacked .stui-column {
        width: 100%;
        padding: 0;
        margin: 0 0 1 0;
    }

    .stui-expander {
        border: round #343444;
        padding: 0 1;
        margin: 1 0;
    }

    .stui-expander:focus {
        border: round #8ab4ff;
        background: #202033;
    }

    .stui-expander-label {
        color: #d7ddff;
        text-style: bold;
        margin: 0 0 1 0;
    }

    .stui-tabs, .stui-tab-panel {
        height: auto;
    }

    .stui-tabs {
        margin: 1 0;
    }

    .stui-tabs-control {
        width: 100%;
        height: 2;
    }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "rerun_script", "Rerun"),
        Binding("tab", "focus_next", "Next widget"),
        Binding("shift+tab", "focus_previous", "Previous widget"),
    ]

    def __init__(self, runtime: Runtime, *, watch: bool = False) -> None:
        super().__init__()
        self.runtime = runtime
        self.watch = watch
        self._multiselect_cursors: dict[str, int] = {}
        self._data_table_cursors: dict[str, int] = {}
        self._text_area_views: dict[
            str,
            tuple[tuple[int, int], tuple[float, float]],
        ] = {}
        self.stui_theme = resolve_theme()
        self.CSS = css_for_theme(type(self).CSS, "high-contrast")
        self.set_class(
            self.stui_theme == "high-contrast",
            HIGH_CONTRAST_CLASS,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield VerticalScroll(id="body")
        yield Footer()

    async def on_mount(self) -> None:
        script_name = visible_terminal_text(self.runtime.script_path.name)
        self.sub_title = f"{script_name} · watching" if self.watch else script_name
        if self.watch:
            self.set_interval(0.5, self._poll_script_change)
        self.runtime.run_script()
        await self.render_runtime()

    async def _poll_script_change(self) -> None:
        if any(isinstance(screen, DataExplorerScreen) for screen in self.screen_stack):
            return
        changed_paths = self.runtime.poll_source_changes()
        if not changed_paths:
            return
        self.runtime.prepare_source_reload(changed_paths)
        await self.action_rerun_script()
        changed_label = ", ".join(
            visible_terminal_text(path.name) for path in changed_paths
        )
        failed = any(
            isinstance(element, ErrorElement)
            for element in self.runtime.elements
        )
        self.notify(
            (
                f"Reload failed for {changed_label}; watching continues"
                if failed
                else f"Reloaded {changed_label}"
            ),
            severity="error" if failed else "information",
            timeout=2,
        )

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        """Expose a fixed set of non-evaluating command palette actions."""
        if isinstance(screen, DataExplorerScreen):
            yield SystemCommand(
                "Close data explorer",
                "Return to the app without changing selection",
                screen.action_close,
            )
            return
        yield SystemCommand(
            "Rerun app",
            "Run the current stui script again",
            self.action_rerun_script,
        )
        yield SystemCommand(
            "Quit",
            "Quit the stui application",
            self.action_quit,
        )
        yield SystemCommand(
            "Toggle theme",
            "Toggle stui's default and high-contrast themes",
            self.action_toggle_theme,
        )
        yield SystemCommand(
            "Clear data cache",
            "Clear cached data for this app runtime",
            self.action_clear_data_cache,
        )
        yield SystemCommand(
            "Clear resource cache",
            "Clear cached resources for this app runtime",
            self.action_clear_resource_cache,
        )
        yield SystemCommand(
            "Focus next widget",
            "Move focus to the next interactive widget",
            self.action_focus_next_widget,
        )
        yield SystemCommand(
            "Diagnostics",
            "Show count-only diagnostics for the current app",
            self.action_show_diagnostics,
        )
        yield SystemCommand(
            "Help",
            "Show key and focused-widget help",
            self.action_show_help_panel,
        )

        if screen is not None:
            for table in screen.query(StuiDataTable):
                if not table.disabled:
                    yield SystemCommand(
                        f"Explore table: {_tab_label(table.stui_key)}",
                        "Search, sort, and inspect displayed rows in fullscreen",
                        partial(self._open_data_explorer, table),
                    )

        tab_targets = []
        for key, index, label in self._command_palette_tab_targets():
            if (
                not isinstance(key, str)
                or not key
                or isinstance(index, bool)
                or not isinstance(index, int)
                or index < 0
                or not isinstance(label, str)
                or not label.strip()
            ):
                continue
            tab_targets.append((key, index, _tab_label(label)))

        visible_labels = [label for _key, _index, label in tab_targets]
        for key, index, visible_label in tab_targets:
            title = f"Switch tab: {visible_label}"
            if visible_labels.count(visible_label) > 1:
                title = f"{title} [{_tab_label(key)}]"
            yield SystemCommand(
                title,
                "Activate this app tab",
                partial(self._switch_command_palette_tab, key, index),
            )

    def _command_palette_tab_targets(self) -> tuple[tuple[str, int, str], ...]:
        """Return safe, renderer-owned tab targets from the current element tree."""
        targets: list[tuple[str, int, str]] = []

        def collect(elements: Iterable[object]) -> None:
            for element in elements:
                if isinstance(element, TabsElement):
                    targets.extend(
                        (element.key, index, label)
                        for index, label in enumerate(element.labels)
                    )
                    collect(element.panes[element.active])
                elif isinstance(element, ColumnsElement):
                    for column in element.columns:
                        collect(column)
                elif isinstance(element, (ContainerElement, SpinnerElement)):
                    collect(element.children or [])
                elif isinstance(element, (ExpanderElement, StatusElement)):
                    if element.expanded:
                        collect(element.children or [])

        collect(self.runtime.elements)
        return tuple(targets)

    async def _switch_command_palette_tab(self, key: str, index: int) -> None:
        self.runtime.set_widget_value(key, index)
        await self.action_rerun_script()

    def action_toggle_theme(self) -> None:
        self.stui_theme = (
            "default" if self.stui_theme == "high-contrast" else "high-contrast"
        )
        self.set_class(
            self.stui_theme == "high-contrast",
            HIGH_CONTRAST_CLASS,
        )
        self.notify(f"Theme: {self.stui_theme}", timeout=2)

    def action_clear_data_cache(self) -> None:
        cache_data._clear_runtime(self.runtime)
        self.notify("Cleared this app's data cache", timeout=2)

    def action_clear_resource_cache(self) -> None:
        cache_resource._clear_runtime(self.runtime)
        self.notify("Cleared this app's resource cache", timeout=2)

    def action_focus_next_widget(self) -> None:
        widgets = [
            widget
            for widget in self.screen.focus_chain
            if getattr(widget, "stui_key", None) is not None
        ]
        if not widgets:
            return
        try:
            current_index = widgets.index(self.focused)
        except ValueError:
            target = widgets[0]
        else:
            target = widgets[(current_index + 1) % len(widgets)]
        self.set_focus(target)

    def action_show_diagnostics(self) -> None:
        snapshot = runtime_snapshot(self.runtime)
        key_counts = snapshot["key_counts"]
        cache = snapshot["cache"]
        self.notify(
            " ".join(
                (
                    f"elements={snapshot['element_count']}",
                    f"widgets={snapshot['widget_count']}",
                    f"session_keys={key_counts['session']}",
                    f"local_modules={snapshot['local_module_count']}",
                    f"watch_files={snapshot['watch_file_count']}",
                    f"cache_entries={cache['total']['entries']}",
                )
            ),
            title="stui diagnostics",
            timeout=8,
        )

    async def action_rerun_script(self) -> None:
        focused_key = self._focused_stui_key()
        if focused_key is not None:
            self.runtime.last_focused_key = focused_key
        self.runtime.run_script()
        await self.render_runtime()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        key = getattr(event.button, "stui_key", None)
        if key is None:
            return
        event.stop()
        self.runtime.press_button(key)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_stui_slider_changed(self, event: StuiSlider.Changed) -> None:
        event.stop()
        self.runtime.set_widget_value(event.key, event.value)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input_widget = getattr(event, "input", None) or event.control
        key = getattr(input_widget, "stui_key", None)
        if key is None:
            return
        event.stop()
        value = event.value
        if isinstance(input_widget, StuiNumberInput):
            value = self._parse_number_input(input_widget, event.value)
        self.runtime.set_widget_value(key, value)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        checkbox = event.checkbox
        key = getattr(checkbox, "stui_key", None)
        if key is None:
            return
        event.stop()
        self.runtime.set_widget_value(key, event.value)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_stui_radio_set_changed(
        self, event: StuiRadioSet.Changed
    ) -> None:
        key = getattr(event.radio, "stui_key", None)
        if key is None:
            return
        if not self._body_is_ready():
            return
        event.stop()
        self.runtime.last_focused_key = key
        self.runtime.set_widget_value(key, event.value)
        self.runtime.run_script()
        await self.render_runtime()

    async def render_runtime(self) -> None:
        body = self.query_one("#body", VerticalScroll)
        for multiselect in self.query(StuiMultiselect):
            self._multiselect_cursors[multiselect.stui_key] = multiselect.stui_cursor
        for data_table in self.query(StuiDataTable):
            self._data_table_cursors[data_table.stui_key] = data_table.cursor_row
        for text_area in self.query(StuiTextArea):
            self._text_area_views[text_area.stui_key] = (
                text_area.cursor_location,
                (text_area.scroll_offset.x, text_area.scroll_offset.y),
            )
        await body.remove_children()
        widgets = [
            self._build_widget(element, self.size.width)
            for element in self.runtime.elements
        ]
        if widgets:
            await body.mount(*widgets)
        self._restore_text_area_views()
        await self._restore_focus()
        self._show_toasts()

    def _show_toasts(self) -> None:
        toasts = self.runtime.toasts
        self.runtime.toasts = []
        for toast in toasts:
            self.notify(visible_terminal_text(toast), timeout=4)

    def _build_widget(self, element, available_width: int | None = None):
        render_width = available_width or self.size.width or 80
        if isinstance(element, TitleElement):
            return Static(
                Text(visible_terminal_text(element.body), style="bold"),
                classes="title",
            )
        if isinstance(element, HeaderElement):
            return Static(
                Text(visible_terminal_text(element.body), style="bold"),
                classes="header",
            )
        if isinstance(element, SubheaderElement):
            return Static(
                Text(visible_terminal_text(element.body), style="bold"),
                classes="subheader",
            )
        if isinstance(element, WriteElement):
            return Static(Text(visible_terminal_text(element.text)), classes="write")
        if isinstance(element, TextElement):
            return Static(Text(visible_terminal_text(element.body)), classes="text")
        if isinstance(element, CaptionElement):
            return Static(
                Text(visible_terminal_text(element.body), style="italic dim"),
                classes="caption",
            )
        if isinstance(element, MarkdownElement):
            return Static(
                Markdown(visible_terminal_text(element.body)),
                classes="markdown",
            )
        if isinstance(element, CodeElement):
            return Static(
                Syntax(
                    visible_terminal_text(element.body),
                    element.language or "text",
                    word_wrap=True,
                    theme="ansi_dark",
                ),
                classes="code",
            )
        if isinstance(element, JsonElement):
            return Static(
                Syntax(
                    visible_terminal_text(element.text),
                    "json",
                    word_wrap=True,
                    theme="ansi_dark",
                ),
                classes="json",
            )
        if isinstance(element, TableElement):
            return Static(
                self._render_table(element, render_width),
                classes="table",
            )
        if isinstance(element, DataTableElement):
            data_table = StuiDataTable(
                element,
                cursor_row=self._data_table_cursors.get(element.key),
                id=dom_id_for_key(element.key),
            )
            data_table.tooltip = (
                "Arrow keys move. Enter or Space selects a row. "
                "F4 opens the fullscreen data explorer. Tab moves focus."
            )
            children = [data_table]
            if element.hidden_rows:
                children.append(
                    Static(
                        f"+{element.hidden_rows} rows",
                        classes="stui-data-table-summary",
                    )
                )
            return Vertical(*children, classes="stui-data-table")
        if isinstance(element, ExceptionElement):
            return Static(
                Panel(
                    Text(
                        visible_terminal_text(element.traceback),
                        style=self._traceback_text_style(),
                        overflow="fold",
                    ),
                    title="Exception",
                    border_style=self._panel_style("error"),
                    title_align="left",
                    padding=(0, 1),
                ),
                classes="exception",
            )
        if isinstance(element, ProgressElement):
            progress_bar = ProgressBar(total=100, show_eta=False)
            progress_bar.update(progress=element.value)
            if element.text is None:
                return Vertical(progress_bar, classes="stui-progress")
            return Vertical(
                Static(
                    _clip_text(element.text, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-progress-label",
                ),
                progress_bar,
                classes="stui-progress",
            )
        if isinstance(element, StatusElement):
            panel = Static(
                Panel(
                    Text(_clip_text(element.label, MAX_STATIC_LABEL_WIDTH)),
                    title=element.state,
                    title_align="left",
                    border_style=self._status_style(element.state),
                    padding=(0, 1),
                ),
                classes=f"stui-status stui-status-{element.state}",
            )
            if not element.expanded:
                return panel
            children = [
                self._build_widget(child, render_width)
                for child in (element.children or [])
            ]
            return Vertical(panel, *children, classes="stui-status")
        if isinstance(element, SpinnerElement):
            panel = Static(
                Panel(
                    Text(_clip_text(element.text, MAX_STATIC_LABEL_WIDTH)),
                    title="spinner",
                    title_align="left",
                    border_style=self._panel_style("accent"),
                    padding=(0, 1),
                ),
                classes="stui-spinner",
            )
            children = [
                self._build_widget(child, render_width)
                for child in (element.children or [])
            ]
            if not children:
                return panel
            return Vertical(panel, *children, classes="stui-spinner")
        if isinstance(element, HelpElement):
            return Static(
                Panel(
                    Text(visible_terminal_text(element.body), overflow="fold"),
                    title="help",
                    title_align="left",
                    border_style=self._panel_style("help"),
                    padding=(0, 1),
                ),
                classes="stui-help",
            )
        if isinstance(element, MetricElement):
            return Static(self._render_metric(element), classes="metric")
        if isinstance(element, BarChartElement):
            return Static(self._render_bar_chart(element), classes="bar-chart")
        if isinstance(element, LineChartElement):
            return Static(self._render_line_chart(element), classes="bar-chart")
        if isinstance(element, ContainerElement):
            children = [
                self._build_widget(child, render_width)
                for child in element.children
            ]
            return Vertical(*children, classes="stui-container")
        if isinstance(element, ColumnsElement):
            column_count = len(element.columns)
            stack_columns = self._should_stack_columns(column_count, render_width)
            child_width = (
                render_width
                if stack_columns
                else max(MIN_RENDERED_COLUMN_WIDTH, render_width // column_count)
            )
            columns = [
                Vertical(
                    *(self._build_widget(child, child_width) for child in column),
                    classes="stui-column",
                )
                for column in element.columns
            ]
            if stack_columns:
                return Vertical(*columns, classes="stui-columns stui-columns-stacked")
            return Horizontal(*columns, classes="stui-columns")
        if isinstance(element, TabsElement):
            tab_widgets = [
                Tab(Content(_tab_label(label)), id=_tab_id(element.key, index))
                for index, label in enumerate(element.labels)
            ]
            for index, tab_widget in enumerate(tab_widgets):
                tab_widget.stui_index = index
            tabs = Tabs(
                *tab_widgets,
                active=_tab_id(element.key, element.active),
                id=dom_id_for_key(element.key),
                classes="stui-tabs-control",
            )
            tabs.stui_key = element.key
            tabs.stui_active_index = element.active
            tabs.tooltip = (
                "Left and Right change tabs. Tab and Shift+Tab move focus."
            )
            children = [
                self._build_widget(child, render_width)
                for child in element.panes[element.active]
            ]
            return Vertical(
                tabs,
                Vertical(*children, classes="stui-tab-panel"),
                classes="stui-tabs",
            )
        if isinstance(element, ExpanderElement):
            if not element.expanded:
                return StuiExpander(element, label_width=render_width)
            children = [
                self._build_widget(child, render_width)
                for child in (element.children or [])
            ]
            return StuiExpander(element, *children, label_width=render_width)
        if isinstance(element, DividerElement):
            width = max(8, min(40, render_width - 4))
            return Static("─" * width, classes="divider")
        if isinstance(element, AlertElement):
            kind = element.kind.lower()
            return Static(
                Panel(
                    Text(visible_terminal_text(element.body), overflow="fold"),
                    title=element.kind,
                    title_align="left",
                    border_style=self._alert_style(kind),
                    padding=(0, 1),
                ),
                classes=f"alert alert-{kind}",
            )
        if isinstance(element, ButtonElement):
            return StuiButton(element)
        if isinstance(element, PathInputElement):
            path_input = StuiPathInput(element)
            path_input.tooltip = (
                "Type a local path. Enter applies. "
                "Tab and Shift+Tab move focus."
            )
            children = [
                Static(
                    _clip_text(element.label, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-field-label",
                ),
                path_input,
            ]
            if element.validation_error is not None:
                children.append(
                    Static(
                        Text(
                            visible_terminal_text(element.validation_error),
                            overflow="fold",
                        ),
                        classes="stui-path-error",
                    )
                )
            return Vertical(*children, classes="stui-field")
        if isinstance(element, TextInputElement):
            text_input = StuiTextInput(element)
            text_input.tooltip = (
                "Type text. Enter submits. Tab and Shift+Tab move focus."
            )
            return Vertical(
                Static(
                    _clip_text(element.label, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-field-label",
                ),
                text_input,
                classes="stui-field",
            )
        if isinstance(element, TextAreaElement):
            text_area = StuiTextArea(element)
            text_area.tooltip = (
                "Enter adds a line. Ctrl+Enter applies and reruns. "
                "Tab and Shift+Tab move focus."
            )
            return Vertical(
                Static(
                    _clip_text(element.label, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-field-label",
                ),
                text_area,
                Static(
                    "Ctrl+Enter applies and reruns; Enter adds a line.",
                    classes="stui-field-hint",
                ),
                classes="stui-field",
            )
        if isinstance(element, NumberInputElement):
            number_input = StuiNumberInput(element)
            number_input.tooltip = (
                "Type a number. Enter submits. Tab and Shift+Tab move focus."
            )
            return Vertical(
                Static(
                    _clip_text(element.label, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-field-label",
                ),
                number_input,
                classes="stui-field",
            )
        if isinstance(element, CheckboxElement):
            checkbox = StuiCheckbox(element)
            checkbox.tooltip = (
                "Space toggles. Tab and Shift+Tab move focus."
            )
            return checkbox
        if isinstance(element, ToggleElement):
            toggle = StuiToggle(element)
            toggle.tooltip = (
                "Space or Enter toggles. Tab and Shift+Tab move focus."
            )
            return Horizontal(
                toggle,
                Static(
                    _clip_text(element.label, MAX_WIDGET_LABEL_WIDTH),
                    classes="stui-toggle-label",
                ),
                classes="stui-toggle",
            )
        if isinstance(element, MultiselectElement):
            multiselect = StuiMultiselect(
                element,
                cursor=self._multiselect_cursors.get(element.key, 0),
            )
            multiselect.tooltip = (
                "Arrow keys move. Space or Enter toggles the highlighted "
                "option. Tab and Shift+Tab move focus."
            )
            return Vertical(
                Static(
                    _clip_text(element.label, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-field-label",
                ),
                multiselect,
                classes="stui-field",
            )
        if isinstance(element, SelectboxElement):
            selectbox = StuiSelectbox(element)
            selectbox.tooltip = (
                "Right/down/Enter choose next. Left/up choose previous. "
                "Tab and Shift+Tab move focus."
            )
            return Vertical(
                Static(
                    _clip_text(element.label, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-field-label",
                ),
                selectbox,
                classes="stui-field",
            )
        if isinstance(element, RadioElement):
            radio = StuiRadioSet(element)
            radio.tooltip = (
                "Arrow keys choose. Tab and Shift+Tab move focus."
            )
            return Vertical(
                Static(
                    _clip_text(element.label, MAX_STATIC_LABEL_WIDTH),
                    classes="stui-field-label",
                ),
                radio,
                classes="stui-field",
            )
        if isinstance(element, SliderElement):
            slider = StuiSlider(
                label=visible_terminal_text(element.label),
                key=element.key,
                min_value=element.min_value,
                max_value=element.max_value,
                value=element.value,
                step=element.step,
                disabled=element.disabled,
                id=dom_id_for_key(element.key),
            )
            slider.tooltip = (
                visible_terminal_text(element.help)
                if element.help is not None
                else "Left/right arrows or h/l adjust. Home/End jump to min/max."
            )
            return slider
        if isinstance(element, ErrorElement):
            return Static(
                Panel(
                    Text(
                        visible_terminal_text(element.traceback),
                        style=self._traceback_text_style(),
                        overflow="fold",
                    ),
                    title=self._script_error_title(element.traceback),
                    border_style=self._panel_style("error"),
                    title_align="left",
                    padding=(0, 1),
                ),
                classes="error",
            )
        return Static(Text(visible_terminal_text(element)))

    async def on_stui_selectbox_changed(
        self, event: StuiSelectbox.Changed
    ) -> None:
        key = getattr(event.selectbox, "stui_key", None)
        if key is None:
            return
        event.stop()
        self.runtime.set_widget_value(key, event.value)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_stui_multiselect_changed(
        self, event: StuiMultiselect.Changed
    ) -> None:
        key = getattr(event.multiselect, "stui_key", None)
        if key is None:
            return
        event.stop()
        self.runtime.set_widget_value(key, event.value)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_data_table_row_selected(
        self,
        event: StuiDataTable.RowSelected,
    ) -> None:
        data_table = event.data_table
        if not isinstance(data_table, StuiDataTable):
            return
        if data_table.stui_selection_mode != "single":
            return
        source_index = data_table.source_index_for_row(event.cursor_row)
        if source_index is None or data_table.disabled:
            return
        event.stop()
        self.runtime.set_widget_value(data_table.stui_key, source_index)
        self.runtime.run_script()
        await self.render_runtime()

    def on_stui_data_table_explore(self, event: StuiDataTable.Explore) -> None:
        event.stop()
        self._open_data_explorer(event.table)

    def _open_data_explorer(self, table: StuiDataTable) -> None:
        if table.disabled or not table.is_mounted:
            return
        if any(isinstance(screen, DataExplorerScreen) for screen in self.screen_stack):
            return
        self.push_screen(
            DataExplorerScreen(table.stui_element, cursor_row=table.cursor_row),
            partial(self._apply_explorer_selection, table),
        )

    async def _apply_explorer_selection(
        self, table: StuiDataTable, source_index: int | None
    ) -> None:
        if source_index is None:
            return
        if not table.is_mounted or table.disabled:
            return
        table.move_cursor(row=table.stui_source_row_indices.index(source_index))
        self.runtime.set_widget_value(table.stui_key, source_index)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        key = getattr(event.switch, "stui_key", None)
        if key is None:
            return
        event.stop()
        self.runtime.set_widget_value(key, event.value)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_stui_text_area_submitted(
        self,
        event: StuiTextArea.Submitted,
    ) -> None:
        key = getattr(event.text_area, "stui_key", None)
        if key is None:
            return
        event.stop()
        self.runtime.last_focused_key = key
        self.runtime.set_widget_value(key, event.value)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_stui_expander_changed(self, event: StuiExpander.Changed) -> None:
        key = getattr(event.expander, "stui_key", None)
        if key is None:
            return
        event.stop()
        self.runtime.set_widget_value(key, event.expanded)
        self.runtime.run_script()
        await self.render_runtime()

    async def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        key = getattr(event.tabs, "stui_key", None)
        index = getattr(event.tab, "stui_index", None)
        if key is None or index is None:
            return
        if index == getattr(event.tabs, "stui_active_index", None):
            return
        event.stop()
        self.runtime.set_widget_value(key, index)
        self.runtime.run_script()
        await self.render_runtime()

    async def _restore_focus(self) -> None:
        key = self.runtime.last_focused_key
        if key is None:
            return
        try:
            widget = self.query(f"#{dom_id_for_key(key)}").first()
        except NoMatches:
            return
        if widget is not None and getattr(widget, "can_focus", False):
            self.set_focus(widget)

    def _focused_stui_key(self) -> str | None:
        focused = self.focused
        if focused is None:
            return None
        return getattr(focused, "stui_key", None)

    def _restore_text_area_views(self) -> None:
        for text_area in self.query(StuiTextArea):
            saved = self._text_area_views.get(text_area.stui_key)
            if saved is None:
                continue
            cursor, scroll = saved
            lines = text_area.text.split("\n")
            row = min(max(cursor[0], 0), len(lines) - 1)
            column = min(max(cursor[1], 0), len(lines[row]))
            text_area.move_cursor((row, column))
            text_area.scroll_to(
                x=scroll[0],
                y=scroll[1],
                animate=False,
                force=True,
                immediate=True,
            )

    def _body_is_ready(self) -> bool:
        try:
            self.query_one("#body", VerticalScroll)
        except NoMatches:
            return False
        return True

    def _should_stack_columns(
        self,
        count: int,
        available_width: int | None = None,
    ) -> bool:
        if count < 2:
            return True
        render_width = available_width or self.size.width or 80
        return render_width // count < MIN_RENDERED_COLUMN_WIDTH

    @staticmethod
    def _parse_number_input(widget: StuiNumberInput, raw: str) -> int | float:
        fallback = widget.stui_fallback
        try:
            value: int | float
            if (
                isinstance(fallback, int)
                and not isinstance(fallback, bool)
                and not isinstance(widget.stui_step, float)
            ):
                value = int(float(raw))
            else:
                value = float(raw)
        except ValueError:
            value = fallback
        if widget.stui_min_value is not None:
            value = max(value, widget.stui_min_value)
        if widget.stui_max_value is not None:
            value = min(value, widget.stui_max_value)
        return value

    @staticmethod
    def _render_table(
        element: TableElement,
        available_width: int = 80,
    ) -> RichTable | Text:
        if available_width and available_width < 16:
            return Text("Table requires a wider terminal.", style="yellow")
        headers, rows = StuiApp._trim_table(
            element.headers,
            element.rows,
            available_width,
        )
        if not rows:
            rows = (("No rows", *("" for _ in headers[1:])),)
        column_count = max(1, len(headers))
        usable_width = max(20, available_width or 80)
        column_width = max(
            MIN_TABLE_COLUMN_WIDTH,
            min(MAX_TABLE_COLUMN_WIDTH, usable_width // column_count - 3),
        )
        table = RichTable(show_lines=False)
        for header in headers:
            table.add_column(
                _clip_text(header, column_width),
                overflow="fold",
                max_width=column_width,
            )
        for row in rows:
            table.add_row(*(_clip_text(cell, column_width * 2) for cell in row))
        return table

    @staticmethod
    def _trim_table(
        headers: tuple[str, ...],
        rows: tuple[tuple[str, ...], ...],
        available_width: int = 80,
    ) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
        if len(headers) <= 1:
            return headers or ("value",), rows
        width = max(20, available_width or 80)
        visible_columns = max(1, width // MIN_TABLE_COLUMN_WIDTH)
        visible_columns = min(MAX_TABLE_COLUMNS, visible_columns, len(headers))
        if visible_columns >= len(headers):
            return headers, rows
        has_existing_marker = headers[-1] == "..." and all(
            len(row) == len(headers) for row in rows
        )
        if has_existing_marker:
            kept_columns = max(1, visible_columns - 1)
            data_headers = headers[:-1]
            if kept_columns >= len(data_headers):
                return headers, rows
            trimmed_headers = (*data_headers[:kept_columns], "...")
            trimmed_rows = tuple((*row[:kept_columns], row[-1]) for row in rows)
            return trimmed_headers, trimmed_rows
        kept_columns = max(1, visible_columns - 1)
        trimmed_headers = (*headers[:kept_columns], "...")
        hidden_count = len(headers) - kept_columns
        trimmed_rows = tuple(
            (*row[:kept_columns], f"+{hidden_count} cols")
            for row in rows
        )
        return trimmed_headers, trimmed_rows

    @staticmethod
    def _render_metric(element: MetricElement) -> Panel:
        body = Text()
        body.append(_clip_text(element.label, MAX_STATIC_LABEL_WIDTH), style="dim")
        body.append("\n")
        body.append(
            _clip_text(element.value, MAX_STATIC_LABEL_WIDTH),
            style="bold #ffffff",
        )
        if element.delta is not None:
            style = "green" if not element.delta.startswith("-") else "red"
            body.append(
                f"  {_clip_text(element.delta, MAX_WIDGET_LABEL_WIDTH)}",
                style=style,
            )
        return Panel(
            body,
            border_style="#343444",
            padding=(0, 1),
        )

    @staticmethod
    def _render_bar_chart(element: BarChartElement) -> Text:
        if element.empty:
            return Text("No chart data", style="dim")
        points = tuple(
            point for point in element.points if math.isfinite(point.value)
        )
        if element.height is not None:
            points = points[: element.height]
        if not points:
            return Text("No chart data", style="dim")

        max_abs = max(abs(point.value) for point in points) or 1
        label_width = min(
            12,
            max(1, max(len(point.label) for point in points)),
        )
        plot_width = min(max(element.width or 28, 1), 60)
        half_width = max(1, plot_width // 2)
        has_negative = any(point.value < 0 for point in points)
        has_positive = any(point.value > 0 for point in points)
        chart = Text()
        for index, point in enumerate(points):
            bar_len = round((abs(point.value) / max_abs) * half_width)
            bar_len = max(1, bar_len) if point.value else 0
            if has_negative and has_positive:
                left = (
                    ("█" * bar_len).rjust(half_width)
                    if point.value < 0
                    else " " * half_width
                )
                right = "█" * bar_len if point.value > 0 else ""
                bar = f"{left}│{right or '·'}"
            else:
                bar = "█" * bar_len if point.value else "·"
            style = "red" if point.value < 0 else "green"
            label = _clip_text(point.label, label_width)
            chart.append(label.rjust(label_width), style="dim")
            chart.append(" │ ", style="dim")
            chart.append(bar, style=style)
            chart.append(f" {point.value:g}")
            if index != len(points) - 1:
                chart.append("\n")
        return chart

    @staticmethod
    def _render_line_chart(element: LineChartElement) -> Text:
        if element.empty:
            return Text("No chart data", style="dim")
        series = tuple(
            item
            for item in element.series
            if any(math.isfinite(value) for value in item.values)
        )
        if element.height is not None:
            series = series[: element.height]
        if not series:
            return Text("No chart data", style="dim")

        label_width = min(
            12,
            max(1, max(len(item.label) for item in series)),
        )
        plot_width = min(max(element.width or 28, 1), 60)
        chart = Text()
        for index, item in enumerate(series):
            values = tuple(value for value in item.values if math.isfinite(value))
            sparkline = StuiApp._sparkline(values, plot_width)
            label = _clip_text(item.label, label_width)
            chart.append(label.rjust(label_width), style="dim")
            chart.append(" │ ", style="dim")
            chart.append(sparkline, style="cyan")
            chart.append(f" {values[-1]:g}" if values else " 0")
            if index != len(series) - 1:
                chart.append("\n")
        return chart

    @staticmethod
    def _sparkline(values: tuple[float, ...], width: int) -> str:
        if not values:
            return "·"
        if len(values) > width:
            step = (len(values) - 1) / max(1, width - 1)
            values = tuple(values[round(index * step)] for index in range(width))
        low = min(values)
        high = max(values)
        if high == low:
            return "─" * max(1, len(values))
        ticks = "▁▂▃▄▅▆▇█"
        scale = len(ticks) - 1
        spread = high - low
        if not math.isfinite(spread):
            max_abs = max(abs(value) for value in values) or 1
            return "".join(
                ticks[
                    StuiApp._clamped_tick_index(
                        ((value / max_abs) + 1) / 2,
                        scale,
                    )
                ]
                for value in values
            )
        return "".join(
            ticks[
                StuiApp._clamped_tick_index(
                    (value - low) / spread,
                    scale,
                )
            ]
            for value in values
        )

    @staticmethod
    def _clamped_tick_index(normalized: float, scale: int) -> int:
        if not math.isfinite(normalized):
            normalized = 0.0
        normalized = min(1.0, max(0.0, normalized))
        return round(normalized * scale)

    def _alert_style(self, kind: str) -> str:
        if self.stui_theme == "high-contrast":
            return self._panel_style("warning" if kind == "warning" else "default")
        return {
            "success": "green",
            "info": "blue",
            "warning": "yellow",
            "error": "red",
        }.get(kind, "white")

    def _status_style(self, state: str) -> str:
        if self.stui_theme == "high-contrast":
            return self._panel_style("warning" if state == "running" else "default")
        return {
            "running": "blue",
            "complete": "green",
            "error": "red",
        }.get(state, "white")

    def _panel_style(self, kind: str) -> str:
        if self.stui_theme == "high-contrast":
            return "#ffff00" if kind in {"accent", "help", "warning"} else "#ffffff"
        return {
            "accent": "cyan",
            "error": "red",
            "help": "#6f7cff",
            "warning": "yellow",
        }.get(kind, "white")

    def _traceback_text_style(self) -> str:
        if self.stui_theme == "high-contrast":
            return "#ffffff"
        return "#ffd7d7"

    @staticmethod
    def _script_error_title(traceback: str) -> str:
        if traceback.startswith("Duplicate widget key"):
            return "Duplicate widget key"
        return "Script error"
