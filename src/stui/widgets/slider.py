from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static

from stui.elements import Number


def _as_decimal(value: Number) -> Decimal:
    return Decimal(str(value))


def _returns_int(*values: Number) -> bool:
    return all(
        isinstance(value, int) and not isinstance(value, bool) for value in values
    )


def snap_value(
    value: Number,
    min_value: Number,
    max_value: Number,
    step: Number,
) -> Number:
    """Clamp a numeric value and snap it to the nearest valid step."""

    if step <= 0:
        raise ValueError("slider step must be greater than 0")
    if max_value < min_value:
        raise ValueError("slider max_value must be greater than or equal to min_value")

    decimal_min = _as_decimal(min_value)
    decimal_max = _as_decimal(max_value)
    decimal_step = _as_decimal(step)
    decimal_value = _as_decimal(value)

    clamped = min(max(decimal_value, decimal_min), decimal_max)
    steps = ((clamped - decimal_min) / decimal_step).to_integral_value(
        rounding=ROUND_HALF_UP
    )
    snapped = decimal_min + steps * decimal_step
    snapped = min(max(snapped, decimal_min), decimal_max)

    if _returns_int(value, min_value, max_value, step):
        return int(snapped)
    return float(snapped)


class StuiSlider(Static, can_focus=True):
    """Clean-room terminal slider for stui's first vertical slice."""

    BINDINGS = [
        Binding("left", "decrease", "Decrease"),
        Binding("h", "decrease", "Decrease", show=False),
        Binding("right", "increase", "Increase"),
        Binding("l", "increase", "Increase", show=False),
        Binding("home", "minimum", "Minimum"),
        Binding("end", "maximum", "Maximum"),
    ]

    class Changed(Message):
        def __init__(self, slider: StuiSlider, key: str, value: Number) -> None:
            super().__init__()
            self.slider = slider
            self.key = key
            self.value = value

    def __init__(
        self,
        *,
        label: str,
        key: str,
        min_value: Number,
        max_value: Number,
        value: Number,
        step: Number,
        disabled: bool = False,
        id: str | None = None,
    ) -> None:
        classes = "stui-slider disabled" if disabled else "stui-slider"
        super().__init__("", id=id, classes=classes, markup=False)
        self.label = label
        self.stui_key = key
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.value = snap_value(value, min_value, max_value, step)
        self.stui_disabled = disabled

    def render(self) -> str:
        width = 14
        if self.max_value == self.min_value:
            ratio = 1.0
        else:
            ratio = float(
                (_as_decimal(self.value) - _as_decimal(self.min_value))
                / (_as_decimal(self.max_value) - _as_decimal(self.min_value))
            )
        filled = max(0, min(width, round(ratio * width)))
        bar = "█" * filled + "░" * (width - filled)
        return f"{self.label}\n[{bar}] {self._format_value(self.value)}"

    def action_decrease(self) -> None:
        self._commit(self.value - self.step)

    def action_increase(self) -> None:
        self._commit(self.value + self.step)

    def action_minimum(self) -> None:
        self._commit(self.min_value)

    def action_maximum(self) -> None:
        self._commit(self.max_value)

    def _commit(self, raw_value: Number) -> None:
        if self.stui_disabled:
            return
        next_value = snap_value(raw_value, self.min_value, self.max_value, self.step)
        if next_value == self.value:
            return
        self.value = next_value
        self.refresh()
        self.post_message(self.Changed(self, self.stui_key, self.value))

    @staticmethod
    def _format_value(value: Number) -> str:
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return f"{value:g}"
