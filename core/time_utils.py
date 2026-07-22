"""Duration conversion and compact presentation helpers."""

from __future__ import annotations

from typing import Iterable


UNIT_TO_MS = {
    "milliseconds": 1,
    "seconds": 1_000,
    "minutes": 60_000,
    "hours": 3_600_000,
}

DELAY_UNITS = tuple(UNIT_TO_MS)
TIMER_UNITS = ("seconds", "minutes", "hours")


def duration_to_ms(value: int, unit: str) -> int:
    if unit not in UNIT_TO_MS:
        raise ValueError(f"Unknown duration unit: {unit}")
    return int(value) * UNIT_TO_MS[unit]


def normalized_value_and_unit(
    duration_ms: int,
    units: Iterable[str],
) -> tuple[int, str]:
    allowed = tuple(units)
    if not allowed:
        raise ValueError("At least one duration unit is required")
    duration_ms = max(0, int(duration_ms))
    for unit in reversed(allowed):
        factor = UNIT_TO_MS[unit]
        if duration_ms >= factor and duration_ms % factor == 0:
            return duration_ms // factor, unit
    unit = allowed[0]
    return duration_ms // UNIT_TO_MS[unit], unit


def format_duration_ms(duration_ms: int) -> str:
    remaining = max(0, int(duration_ms))
    if remaining < 1_000:
        return f"{remaining} ms"

    if remaining % 1_000:
        seconds = remaining / 1_000
        return f"{seconds:g} s"

    total_seconds = remaining // 1_000
    hours, remainder = divmod(total_seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    if seconds or not parts:
        parts.append(f"{seconds} s")
    return " ".join(parts)


def format_countdown(duration_ms: int) -> str:
    total_seconds = max(0, (int(duration_ms) + 999) // 1_000)
    hours, remainder = divmod(total_seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
