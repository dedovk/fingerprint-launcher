import pytest

from core.action_registry import (
    ACTION_DEFINITIONS,
    ACTION_SCHEMA_VERSION,
    ActionValidationError,
    UnknownActionError,
    build_command_data,
    format_action_summary,
    normalize_command_data,
    validate_command_data,
)
from ui.i18n import action_labels


def test_registry_contains_all_existing_actions_in_original_order():
    assert [definition.command_type for definition in ACTION_DEFINITIONS] == [
        "launch_app",
        "open_url",
        "hotkey",
        "shell",
        "lock_screen",
        "minimize_all",
        "shutdown",
        "restart",
        "sleep",
        "paste_text",
        "delay",
        "quick_timer",
    ]


def test_build_data_adds_schema_version_and_action_defaults():
    assert build_command_data("launch_app", "Code.exe") == {
        "schema_version": ACTION_SCHEMA_VERSION,
        "args": "",
        "path": "Code.exe",
    }


def test_legacy_data_is_normalized_without_losing_values():
    assert normalize_command_data("open_url", {"url": "https://example.com"}) == {
        "url": "https://example.com",
        "schema_version": ACTION_SCHEMA_VERSION,
    }


def test_delay_and_timer_validate_and_format_normalized_durations():
    assert validate_command_data("delay", {"duration_ms": 1_500})["duration_ms"] == 1_500
    assert format_action_summary("delay", {"duration_ms": 1_500}) == "1.5 s"
    assert format_action_summary(
        "quick_timer",
        {"duration_ms": 7_200_000, "message": "Tea"},
    ) == "2 h - Tea"


@pytest.mark.parametrize("command_type", ["delay", "quick_timer"])
@pytest.mark.parametrize("duration_ms", [0, -1, 2_592_000_001, 1.5, True])
def test_duration_actions_reject_invalid_values(command_type, duration_ms):
    with pytest.raises(ActionValidationError):
        validate_command_data(command_type, {"duration_ms": duration_ms})


def test_shared_validator_rejects_missing_required_value():
    with pytest.raises(ActionValidationError):
        validate_command_data("open_url", {})


def test_shared_validator_rejects_future_schema_version():
    with pytest.raises(ActionValidationError):
        validate_command_data(
            "open_url",
            {"schema_version": 2, "url": "https://example.com"},
        )


def test_unknown_action_is_reported_by_validator():
    with pytest.raises(UnknownActionError):
        validate_command_data("unknown", {})


def test_formatter_uses_value_or_localized_fallback():
    assert format_action_summary("hotkey", {"keys": "ctrl+z"}, "Press hotkey") == "ctrl+z"
    assert format_action_summary("sleep", {}, "Sleep mode") == "Sleep mode"


def test_clipboard_action_has_accurate_name_in_all_languages():
    assert action_labels("uk")["paste_text"] == "Копіювання тексту в буфер обміну"
    assert action_labels("en")["paste_text"] == "Copy text to clipboard"
    assert action_labels("ru")["paste_text"] == "Копирование текста в буфер обмена"
    assert action_labels("fr")["paste_text"] == "Copier le texte dans le presse-papiers"
    assert action_labels("es")["paste_text"] == "Copiar texto al portapapeles"


@pytest.mark.parametrize(
    ("language", "restart", "minimize_all"),
    [
        ("uk", "Перезавантаження", "Згорнути всі вікна"),
        ("en", "Restart computer", "Minimize all windows"),
        ("ru", "Перезагрузка", "Свернуть все окна"),
        ("fr", "Redémarrer l'ordinateur", "Réduire toutes les fenêtres"),
        ("es", "Reiniciar el equipo", "Minimizar todas las ventanas"),
    ],
)
def test_new_system_actions_are_translated(language, restart, minimize_all):
    labels = action_labels(language)
    assert labels["restart"] == restart
    assert labels["minimize_all"] == minimize_all
