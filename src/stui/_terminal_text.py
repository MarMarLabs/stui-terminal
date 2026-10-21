from __future__ import annotations

from typing import Any


def visible_terminal_text(value: Any) -> str:
    """Make terminal controls and surrogates visible, preserving editable text."""
    visible: list[str] = []
    for character in str(value):
        codepoint = ord(character)
        if (codepoint < 0x20 and codepoint not in {0x09, 0x0A}) or (
            0x7F <= codepoint <= 0x9F
        ):
            visible.append(f"\\x{codepoint:02x}")
        elif 0xDC80 <= codepoint <= 0xDCFF:
            visible.append(f"\\x{codepoint - 0xDC00:02x}")
        elif 0xD800 <= codepoint <= 0xDFFF:
            visible.append(f"\\u{codepoint:04x}")
        else:
            visible.append(character)
    return "".join(visible)
