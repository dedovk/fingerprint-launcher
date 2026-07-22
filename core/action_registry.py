"""Definitions, validation, and presentation metadata for launcher actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from core.time_utils import format_duration_ms


ACTION_SCHEMA_VERSION = 1
MAX_DELAY_DURATION_MS = 24 * 60 * 60 * 1_000
MAX_TIMER_DURATION_MS = 30 * 24 * 60 * 60 * 1_000


class ActionRegistryError(ValueError):
    """Base error raised for invalid or unknown actions."""


class UnknownActionError(ActionRegistryError):
    pass


class ActionValidationError(ActionRegistryError):
    pass


Validator = Callable[[dict[str, Any]], None]
SummaryFormatter = Callable[[dict[str, Any], str], str]


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


def _validate_duration(field_name: str, maximum_ms: int) -> Validator:
    def validate(data: dict[str, Any]) -> None:
        value = data.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ActionValidationError(f"{field_name} must be an integer")
        if not 1 <= value <= maximum_ms:
            raise ActionValidationError(
                f"{field_name} must be between 1 and {maximum_ms} milliseconds"
            )

    return validate


def _validate_quick_timer(data: dict[str, Any]) -> None:
    _validate_duration("duration_ms", MAX_TIMER_DURATION_MS)(data)
    if not isinstance(data.get("message", ""), str):
        raise ActionValidationError("message must be a string")
    if not isinstance(data.get("sound_path", ""), str):
        raise ActionValidationError("sound_path must be a string")


def _validate_volume_change(data: dict[str, Any]) -> None:
    direction = data.get("direction")
    if direction not in {"increase", "decrease"}:
        raise ActionValidationError("direction must be increase or decrease")
    amount = data.get("amount_percent")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ActionValidationError("amount_percent must be an integer")
    if not 1 <= amount <= 100:
        raise ActionValidationError("amount_percent must be between 1 and 100")


def _duration_summary(data: dict[str, Any], fallback: str) -> str:
    duration_ms = data.get("duration_ms")
    if isinstance(duration_ms, int) and not isinstance(duration_ms, bool):
        return format_duration_ms(duration_ms)
    return fallback


def _timer_summary(data: dict[str, Any], fallback: str) -> str:
    duration = _duration_summary(data, fallback)
    message = str(data.get("message") or "").strip()
    return f"{duration} - {message}" if message else duration


def _volume_summary(data: dict[str, Any], fallback: str) -> str:
    amount = data.get("amount_percent")
    direction = data.get("direction")
    if isinstance(amount, int) and not isinstance(amount, bool):
        prefix = "+" if direction == "increase" else "-"
        return f"{prefix}{amount}%"
    return fallback


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
    summary_formatter: SummaryFormatter | None = None

    @property
    def requires_value(self) -> bool:
        return self.value_field is not None

    def build_data(self, value: str = "") -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": ACTION_SCHEMA_VERSION,
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
        for key, value in self.defaults.items():
            normalized.setdefault(key, value)
        return normalized

    def validate_data(self, data: Any) -> dict[str, Any]:
        normalized = self.normalize_data(data)
        if normalized["schema_version"] != ACTION_SCHEMA_VERSION:
            raise ActionValidationError(
                f"Unsupported action schema version: {normalized['schema_version']}"
            )
        if self.validator is not None:
            self.validator(normalized)
        return normalized

    def summary(self, data: Any, fallback_label: str) -> str:
        normalized = self.normalize_data(data)
        if self.summary_formatter is not None:
            return self.summary_formatter(normalized, fallback_label)
        if self.value_field is not None:
            value = normalized.get(self.value_field)
            if value is not None and str(value).strip():
                return str(value)
        return fallback_label


def _normalize_schema_version(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return ACTION_SCHEMA_VERSION


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
        "minimize_all", "minimize_all", "system",
        keywords=(
            "minimize", "all", "windows", "desktop", "show desktop",
            "згорнути", "усі", "вікна", "робочий стіл",
            "свернуть", "все", "окна", "рабочий стол",
            "réduire", "toutes", "fenêtres", "bureau",
            "minimizar", "todas", "ventanas", "escritorio",
        ),
    ),
    ActionDefinition(
        "toggle_mute", "toggle_mute", "system",
        keywords=(
            "mute", "unmute", "toggle", "sound", "audio",
            "звук", "вимкнути", "увімкнути", "тиша",
            "звук", "выключить", "включить", "без звука",
            "son", "couper", "rétablir", "muet",
            "sonido", "silenciar", "activar", "audio",
        ),
    ),
    ActionDefinition(
        "change_volume", "change_volume", "system", editor="volume",
        defaults={"direction": "increase", "amount_percent": 10},
        keywords=(
            "volume", "sound", "audio", "increase", "decrease", "percent",
            "гучність", "звук", "збільшити", "зменшити", "відсоток",
            "громкость", "увеличить", "уменьшить", "процент",
            "volume", "augmenter", "diminuer", "pourcentage",
            "volumen", "subir", "bajar", "porcentaje",
        ),
        validator=_validate_volume_change,
        summary_formatter=_volume_summary,
    ),
    ActionDefinition(
        "close_active_window", "close_active_window", "system",
        keywords=(
            "close", "active", "window", "alt f4",
            "закрити", "активне", "вікно",
            "закрыть", "активное", "окно",
            "fermer", "fenêtre", "active",
            "cerrar", "ventana", "activa",
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
        "restart", "restart", "system",
        keywords=(
            "restart", "reboot", "computer", "windows",
            "перезавантаження", "перезавантажити", "комп'ютер",
            "перезагрузка", "перезагрузить", "компьютер",
            "redémarrer", "redémarrage", "ordinateur",
            "reiniciar", "reinicio", "equipo", "ordenador",
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
    ActionDefinition(
        "delay", "delay", "macros", editor="duration",
        defaults={"duration_ms": 1_000},
        keywords=(
            "delay", "wait", "pause", "milliseconds", "seconds", "minutes", "hours",
            "затримка", "чекати", "пауза", "мілісекунди", "секунди", "хвилини", "години",
            "задержка", "ждать", "миллисекунды", "секунды", "минуты", "часы",
            "délai", "attendre", "pause", "millisecondes", "secondes", "minutes", "heures",
            "retraso", "esperar", "pausa", "milisegundos", "segundos", "minutos", "horas",
        ),
        validator=_validate_duration("duration_ms", MAX_DELAY_DURATION_MS),
        summary_formatter=_duration_summary,
    ),
    ActionDefinition(
        "quick_timer", "quick_timer", "macros", editor="timer",
        defaults={"duration_ms": 60_000, "message": "", "sound_path": ""},
        keywords=(
            "timer", "reminder", "alarm", "countdown",
            "таймер", "нагадування", "відлік",
            "таймер", "напоминание", "отсчёт",
            "minuteur", "rappel", "compte à rebours",
            "temporizador", "recordatorio", "cuenta atrás",
        ),
        validator=_validate_quick_timer,
        summary_formatter=_timer_summary,
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
