"""Definitions, validation, and presentation metadata for launcher actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


ACTION_SCHEMA_VERSION = 1
MAX_ACTION_DELAY_SECONDS = 24 * 60 * 60


class ActionRegistryError(ValueError):
    """Base error raised for invalid or unknown actions."""


class UnknownActionError(ActionRegistryError):
    pass


class ActionValidationError(ActionRegistryError):
    pass


Validator = Callable[[dict[str, Any]], None]


def _require_string(field_name: str) -> Validator:
    def validate(data: dict[str, Any]) -> None:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ActionValidationError(f"{field_name} must be a non-empty string")

    return validate


def _validate_launch_app(data: dict[str, Any]) -> None:
    _require_string("path")(data)
    if not isinstance(data.get("args", ""), str):
        raise ActionValidationError("args must be a string")


def _validate_shell(data: dict[str, Any]) -> None:
    _require_string("cmd")(data)
    if not isinstance(data.get("hidden", True), bool):
        raise ActionValidationError("hidden must be a boolean")


@dataclass(frozen=True)
class ActionDefinition:
    command_type: str
    label_key: str
    category: str
    value_field: str | None = None
    editor: str = "text"
    defaults: Mapping[str, Any] = field(default_factory=dict)
    keywords: tuple[str, ...] = ()
    validator: Validator | None = None

    @property
    def requires_value(self) -> bool:
        return self.value_field is not None

    def build_data(self, value: str = "") -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": ACTION_SCHEMA_VERSION,
            "delay_before": 0.0,
            "delay_after": 0.0,
            **dict(self.defaults),
        }
        if self.value_field is not None:
            data[self.value_field] = value
        return data

    def normalize_data(self, data: Any) -> dict[str, Any]:
        normalized = dict(data) if isinstance(data, dict) else {}
        normalized["schema_version"] = _normalize_schema_version(
            normalized.get("schema_version")
        )
        normalized.setdefault("delay_before", 0.0)
        normalized.setdefault("delay_after", 0.0)
        for key, value in self.defaults.items():
            normalized.setdefault(key, value)
        return normalized

    def validate_data(self, data: Any) -> dict[str, Any]:
        normalized = self.normalize_data(data)
        if normalized["schema_version"] != ACTION_SCHEMA_VERSION:
            raise ActionValidationError(
                f"Unsupported action schema version: {normalized['schema_version']}"
            )
        _validate_delays(normalized)
        if self.validator is not None:
            self.validator(normalized)
        return normalized

    def summary(self, data: Any, fallback_label: str) -> str:
        normalized = self.normalize_data(data)
        if self.value_field is not None:
            value = normalized.get(self.value_field)
            if value is not None and str(value).strip():
                return str(value)
        return fallback_label


def _normalize_schema_version(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return ACTION_SCHEMA_VERSION


def _validate_delays(data: dict[str, Any]) -> None:
    for field_name in ("delay_before", "delay_after"):
        value = data.get(field_name, 0.0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ActionValidationError(f"{field_name} must be a number")
        if not 0 <= float(value) <= MAX_ACTION_DELAY_SECONDS:
            raise ActionValidationError(
                f"{field_name} must be between 0 and {MAX_ACTION_DELAY_SECONDS} seconds"
            )


ACTION_DEFINITIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition(
        "launch_app", "launch_app", "basic", value_field="path", editor="file",
        defaults={"args": ""},
        keywords=(
            "app", "application", "program", "file", "exe",
            "програма", "відкрити", "файл",
            "программа", "открыть",
            "ouvrir", "application", "fichier",
            "abrir", "aplicación", "programa", "archivo",
        ),
        validator=_validate_launch_app,
    ),
    ActionDefinition(
        "open_url", "open_url", "basic", value_field="url",
        keywords=(
            "url", "website", "browser", "web", "link",
            "сайт", "посилання", "браузер", "ссылка",
            "site", "navigateur", "lien", "sitio", "navegador", "enlace",
        ),
        validator=_require_string("url"),
    ),
    ActionDefinition(
        "hotkey", "hotkey", "macros", value_field="keys", editor="hotkey",
        keywords=(
            "hotkey", "shortcut", "keyboard", "keys",
            "клавіші", "комбінація", "гаряча",
            "клавиши", "сочетание", "горячая",
            "raccourci", "clavier", "touche", "atajo", "teclado", "teclas",
        ),
        validator=_require_string("keys"),
    ),
    ActionDefinition(
        "shell", "shell", "macros", value_field="cmd", defaults={"hidden": True},
        keywords=(
            "powershell", "terminal", "script", "command",
            "команда", "скрипт", "виконати", "выполнить",
            "commande", "exécuter", "comando", "ejecutar", "consola",
        ),
        validator=_validate_shell,
    ),
    ActionDefinition(
        "lock_screen", "lock_screen", "system",
        keywords=(
            "lock", "screen", "windows", "екран", "блокування", "блокировка",
            "verrouiller", "écran", "verrouillage", "bloquear", "pantalla", "bloqueo",
        ),
    ),
    ActionDefinition(
        "shutdown", "shutdown", "system",
        keywords=(
            "shutdown", "power", "off", "вимкнути", "комп'ютер", "выключить", "компьютер",
            "éteindre", "arrêt", "ordinateur", "apagar", "equipo", "ordenador",
        ),
    ),
    ActionDefinition(
        "sleep", "sleep", "system",
        keywords=(
            "sleep", "suspend", "standby", "сон", "режим сну",
            "veille", "suspendre", "suspensión", "reposo", "suspender",
        ),
    ),
    ActionDefinition(
        "paste_text", "paste_text", "macros", value_field="text",
        keywords=(
            "copy", "clipboard", "text", "буфер", "копіювати", "копіювання",
            "копировать", "копирование", "обмен",
            "copier", "presse-papiers", "texte", "copiar", "portapapeles", "texto",
        ),
        validator=_require_string("text"),
    ),
)


ACTION_REGISTRY: dict[str, ActionDefinition] = {
    definition.command_type: definition for definition in ACTION_DEFINITIONS
}


def get_action_definition(command_type: str) -> ActionDefinition:
    try:
        return ACTION_REGISTRY[command_type]
    except KeyError as exc:
        raise UnknownActionError(f"Unknown command type: {command_type}") from exc


def normalize_command_data(command_type: str, data: Any) -> dict[str, Any]:
    definition = ACTION_REGISTRY.get(command_type)
    if definition is not None:
        return definition.normalize_data(data)
    normalized = dict(data) if isinstance(data, dict) else {}
    normalized["schema_version"] = _normalize_schema_version(
        normalized.get("schema_version")
    )
    normalized.setdefault("delay_before", 0.0)
    normalized.setdefault("delay_after", 0.0)
    return normalized


def validate_command_data(command_type: str, data: Any) -> dict[str, Any]:
    return get_action_definition(command_type).validate_data(data)


def build_command_data(command_type: str, value: str = "") -> dict[str, Any]:
    return get_action_definition(command_type).build_data(value)


def format_action_summary(
    command_type: str,
    data: Any,
    fallback_label: str | None = None,
) -> str:
    definition = ACTION_REGISTRY.get(command_type)
    fallback = fallback_label or command_type
    if definition is None:
        return fallback
    return definition.summary(data, fallback)
