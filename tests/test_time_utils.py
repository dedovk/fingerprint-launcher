import pytest

from core.time_utils import (
    duration_to_ms,
    format_countdown,
    format_duration_ms,
    normalized_value_and_unit,
)


def test_duration_conversion_and_normalization():
    assert duration_to_ms(1500, "milliseconds") == 1_500
    assert duration_to_ms(120, "minutes") == 7_200_000
    assert normalized_value_and_unit(7_200_000, ("seconds", "minutes", "hours")) == (2, "hours")
    assert normalized_value_and_unit(90_000, ("seconds", "minutes", "hours")) == (90, "seconds")


def test_duration_formatting():
    assert format_duration_ms(1_500) == "1.5 s"
    assert format_duration_ms(7_200_000) == "2 h"
    assert format_countdown(3_661_000) == "1:01:01"
    assert format_countdown(61_000) == "01:01"


def test_unknown_duration_unit_is_rejected():
    with pytest.raises(ValueError):
        duration_to_ms(1, "days")
