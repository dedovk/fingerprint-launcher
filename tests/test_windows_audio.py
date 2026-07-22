from contextlib import nullcontext
from unittest.mock import Mock, patch

import pytest

from core.windows_audio import change_volume, toggle_mute


def test_toggle_mute_inverts_current_endpoint_state():
    endpoint = Mock()
    endpoint.get_muted.return_value = False
    with patch(
        "core.windows_audio._default_endpoint_volume",
        return_value=nullcontext(endpoint),
    ):
        assert toggle_mute() is True

    endpoint.set_muted.assert_called_once_with(True)


@pytest.mark.parametrize(
    ("current", "delta", "expected_scalar", "expected_percent"),
    [
        (0.40, 15, 0.55, 55),
        (0.40, -25, 0.15, 15),
        (0.95, 20, 1.0, 100),
        (0.05, -20, 0.0, 0),
    ],
)
def test_change_volume_is_relative_and_clamped(
    current, delta, expected_scalar, expected_percent
):
    endpoint = Mock()
    endpoint.get_volume.return_value = current
    with patch(
        "core.windows_audio._default_endpoint_volume",
        return_value=nullcontext(endpoint),
    ):
        assert change_volume(delta) == expected_percent

    endpoint.set_volume.assert_called_once()
    assert endpoint.set_volume.call_args.args[0] == pytest.approx(expected_scalar)


@pytest.mark.parametrize("delta", [0, -101, 101, 1.5, True])
def test_change_volume_rejects_invalid_delta(delta):
    with pytest.raises(ValueError):
        change_volume(delta)
