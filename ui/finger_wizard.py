"""Dialog for binding a recognized finger to an action."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QObject, QSize, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QKeySequence, QPixmap

import time

from core.action_registry import (
    ACTION_DEFINITIONS,
    ActionValidationError,
    build_command_data,
    format_action_summary,
    get_action_definition,
    validate_command_data,
)
from core.database import Database
from core.winbio import (
    WINBIO_ID_TYPE_GUID,
    WINBIO_POOL_PRIVATE,
    WINBIO_POOL_SYSTEM,
    WINBIO_E_NO_MATCH,
    WINBIO_E_UNKNOWN_ID,
    S_OK,
    WinBioError,
    WinBioSession,
    enumerate_biometric_units,
    format_hresult,
    identity_key,
)
from ui.action_picker import ActionPicker
from ui.i18n import (
    action_labels,
    localized_finger_name,
    localized_winbio_message,
    tr,
)
from ui.theme import THEME, app_qss, icon


DATA_FREE_ACTIONS = {
    definition.command_type
    for definition in ACTION_DEFINITIONS
    if not definition.requires_value
}
WIZARD_WIDTH = 540
WIZARD_COMPACT_HEIGHT = 427
WIZARD_ACTION_EMPTY_HEIGHT = 560
WIZARD_ACTION_HEIGHT = 643
WIZARD_ACTION_BUTTON_WIDE = 476
WIZARD_BROWSE_BUTTON_WIDTH = 126
WIZARD_CONTROL_GAP = 8


def _wizard_button(text: str, kind: str, icon_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", kind)
    if icon_name:
        button.setProperty("iconName", icon_name)
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(14, 14))
    return button


class WizardTitleBar(QFrame):
    def __init__(self, parent: QDialog, title: str) -> None:
        super().__init__(parent)
        self.window = parent
        self.drag_pos = None


class CurrentPageStack(QStackedWidget):
    def sizeHint(self) -> QSize:  # type: ignore[override]
        widget = self.currentWidget()
        return widget.sizeHint() if widget is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        widget = self.currentWidget()
        return widget.minimumSizeHint() if widget is not None else super().minimumSizeHint()
        self.setFixedHeight(45)
        self.setProperty("role", "titleWizard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(8)
        app_icon = QLabel("FL")
        app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon.setFixedSize(16, 16)
        app_icon.setStyleSheet("background:#1D74F7;color:white;border-radius:2px;font-size:8px;font-weight:700;")
        layout.addWidget(app_icon)
        self.title = QLabel(title)
        self.title.setProperty("role", "wizardTitle")
        layout.addWidget(self.title)
        layout.addStretch()
        self.close_btn = QPushButton()
        self.close_btn.setProperty("iconName", "close_wizard_fixed")
        self.close_btn.setIcon(icon("close_wizard_fixed"))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.setProperty("role", "wizardWindowButton")
        self.close_btn.clicked.connect(parent.close)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.drag_pos = None


class CleanWizardTitleBar(QFrame):
    def __init__(self, parent: QDialog, title: str) -> None:
        super().__init__(parent)
        self.window = parent
        self.drag_pos = None
        self.setFixedHeight(45)
        self.setProperty("role", "titleWizard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(8)
        app_icon = QLabel("FL")
        app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon.setFixedSize(16, 16)
        app_icon.setStyleSheet("background:#1D74F7;color:white;border-radius:2px;font-size:8px;font-weight:700;")
        layout.addWidget(app_icon)
        self.title = QLabel(title)
        self.title.setProperty("role", "wizardTitle")
        layout.addWidget(self.title)
        layout.addStretch()
        self.close_btn = QPushButton()
        self.close_btn.setProperty("iconName", "close_wizard_fixed")
        self.close_btn.setIcon(icon("close_wizard_fixed"))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.setProperty("role", "wizardWindowButton")
        self.close_btn.clicked.connect(parent.close)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.drag_pos = None


class WizardPageStack(QStackedWidget):
    def sizeHint(self) -> QSize:  # type: ignore[override]
        widget = self.currentWidget()
        return widget.sizeHint() if widget is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        widget = self.currentWidget()
        return widget.minimumSizeHint() if widget is not None else super().minimumSizeHint()


class HotkeyEdit(QLineEdit):
    """QLineEdit for keyboard combinations.

    The user presses a key combination (e.g. Ctrl+Alt+T) and the widget
    displays it in the format expected by the ``keyboard`` library
    (e.g. "ctrl+alt+t"). Manual typing is also supported for combinations
    that Windows reserves globally (for example "win+r").
    """

    # Qt key → keyboard-library name overrides for keys whose QKeySequence
    # string differs from what the ``keyboard`` library expects.
    _KEY_MAP: dict[int, str] = {
        int(Qt.Key.Key_Return):    "enter",
        int(Qt.Key.Key_Enter):     "enter",
        int(Qt.Key.Key_Escape):    "esc",
        int(Qt.Key.Key_Tab):       "tab",
        int(Qt.Key.Key_Backspace): "backspace",
        int(Qt.Key.Key_Delete):    "delete",
        int(Qt.Key.Key_Insert):    "insert",
        int(Qt.Key.Key_Home):      "home",
        int(Qt.Key.Key_End):       "end",
        int(Qt.Key.Key_PageUp):    "page up",
        int(Qt.Key.Key_PageDown):  "page down",
        int(Qt.Key.Key_Left):      "left",
        int(Qt.Key.Key_Right):     "right",
        int(Qt.Key.Key_Up):        "up",
        int(Qt.Key.Key_Down):      "down",
        int(Qt.Key.Key_Space):     "space",
        int(Qt.Key.Key_F1):  "f1",  int(Qt.Key.Key_F2):  "f2",
        int(Qt.Key.Key_F3):  "f3",  int(Qt.Key.Key_F4):  "f4",
        int(Qt.Key.Key_F5):  "f5",  int(Qt.Key.Key_F6):  "f6",
        int(Qt.Key.Key_F7):  "f7",  int(Qt.Key.Key_F8):  "f8",
        int(Qt.Key.Key_F9):  "f9",  int(Qt.Key.Key_F10): "f10",
        int(Qt.Key.Key_F11): "f11", int(Qt.Key.Key_F12): "f12",
        int(Qt.Key.Key_Print):      "print screen",
        int(Qt.Key.Key_ScrollLock): "scroll lock",
        int(Qt.Key.Key_Pause):      "pause",
        int(Qt.Key.Key_CapsLock):   "caps lock",
        int(Qt.Key.Key_NumLock):    "num lock",
        int(Qt.Key.Key_Slash):      "/",
        int(Qt.Key.Key_Backslash):  "\\",
    }

    # Standalone modifier keys — ignore presses of these alone.
    _MODIFIER_KEYS = {
        int(Qt.Key.Key_Control), int(Qt.Key.Key_Alt),
        int(Qt.Key.Key_Shift),   int(Qt.Key.Key_Meta),
        int(Qt.Key.Key_AltGr),
    }

    _TOKEN_ALIASES: dict[str, str] = {
        "win": "windows",
        "meta": "windows",
        "cmd": "windows",
        "super": "windows",
        "lwin": "windows",
        "rwin": "windows",
        "pgup": "page up",
        "pageup": "page up",
        "pgdn": "page down",
        "pagedown": "page down",
        "ins": "insert",
        "del": "delete",
        "return": "enter",
        "printscreen": "print screen",
        "scrolllock": "scroll lock",
        "capslock": "caps lock",
        "numlock": "num lock",
    }

    def __init__(self, parent=None, capture_only: bool = False, require_modifier: bool = False) -> None:
        super().__init__(parent)
        self.capture_only = capture_only
        self.require_modifier = require_modifier
        self.setReadOnly(capture_only)
        self.setPlaceholderText(
            "Press or type a hotkey (e.g. ctrl+shift+a, win+r)")

    @classmethod
    def normalize_hotkey(cls, raw: str) -> str:
        tokens: list[str] = []
        for raw_token in raw.split("+"):
            token = raw_token.strip().lower()
            compact = token.replace(" ", "")
            if not compact:
                continue
            tokens.append(cls._TOKEN_ALIASES.get(compact, compact))

        unique_tokens: list[str] = []
        for token in tokens:
            if token not in unique_tokens:
                unique_tokens.append(token)
        return "+".join(unique_tokens)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = int(event.key())
        if key in self._MODIFIER_KEYS:
            return  # Wait for the actual key alongside the modifier.

        modifiers = event.modifiers()
        capture_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
            | Qt.KeyboardModifier.ShiftModifier
        )
        if not self.capture_only and not (modifiers & capture_modifiers):
            super().keyPressEvent(event)
            return

        parts: list[str] = []
        has_primary_modifier = False
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
            has_primary_modifier = True
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
            has_primary_modifier = True
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")
            has_primary_modifier = True

        if self.capture_only and self.require_modifier and not has_primary_modifier:
            return

        key_name = self._KEY_MAP.get(key)
        if key_name is None:
            # Fall back to Qt's own string representation (letters, digits, …).
            key_name = QKeySequence(key).toString().lower()

        if key_name:
            parts.append(key_name)

        if parts:
            self.setText(self.normalize_hotkey("+".join(parts)))

    def keyReleaseEvent(self, event) -> None:  # type: ignore[override]
        pass  # Keep the captured text; do not clear on release.

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        self.setText(self.normalize_hotkey(self.text()))
        super().focusOutEvent(event)


class _CaptureWorker(QObject):
    """Runs on a background thread so the wizard UI stays responsive."""

    captured = pyqtSignal(dict)
    failed = pyqtSignal(str, str)

    def __init__(self, lang: str, timeout: float = 30.0) -> None:
        super().__init__()
        self.lang = lang
        self.timeout = timeout
        self._cancelled = False
        self._session = None

    @pyqtSlot()
    def run(self) -> None:
        try:
            self._session = self._open_session()
            if self._session is None:
                self.failed.emit("error", tr(self.lang, "sensor_unavailable"))
                return

            result = self._wait_for_finger()
            if result is not None:
                self.captured.emit(result)
        except TimeoutError:
            self.failed.emit("timeout", tr(self.lang, "timeout"))
        except WinBioError as exc:
            self.failed.emit(
                "error",
                f"{format_hresult(exc.hr)}: {localized_winbio_message(self.lang, exc.hr)}",
            )
        except RuntimeError as exc:
            self.failed.emit("error", str(exc))
        except Exception as exc:
            self.failed.emit("error", str(exc))
        finally:
            if self._session:
                self._session.close()

    def _open_session(self) -> WinBioSession | None:
        try:
            units = enumerate_biometric_units()
        except Exception:
            return None

        has_private = any(u.pool_type == WINBIO_POOL_PRIVATE for u in units)
        pools = [WINBIO_POOL_PRIVATE] if has_private else []
        pools.append(WINBIO_POOL_SYSTEM)

        for pool in pools:
            try:
                return WinBioSession(pool)
            except Exception:
                pass
        return None

    def _wait_for_finger(self) -> dict | None:
        deadline = time.monotonic() + self.timeout
        while not self._cancelled:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(tr(self.lang, "timeout"))

            timeout_ms = int(min(500, remaining * 1000))
            try:
                result = self._session.identify(timeout_ms=timeout_ms)
            except WinBioError:
                raise
            except Exception as exc:
                raise RuntimeError(str(exc))

            if result is None:
                continue

            if result.hr == S_OK:
                guid = result.guid or ""
                return {
                    "type": "finger_identified",
                    "guid": guid,
                    "identity_type": result.identity_type,
                    "identity_value": result.identity_value,
                    "sub_factor": result.sub_factor,
                    "finger_name": localized_finger_name(self.lang, result.sub_factor),
                }
            elif result.hr == WINBIO_E_UNKNOWN_ID:
                raise RuntimeError(tr(self.lang, "unknown_hello"))
            elif result.hr == WINBIO_E_NO_MATCH:
                continue

        return None

    def cancel(self) -> None:
        self._cancelled = True
        if self._session:
            self._session.cancel()


class FingerWizard(QDialog):
    def __init__(self, db: Database, parent=None, existing: dict | None = None, lang: str = "uk") -> None:
        super().__init__(parent)
        self.db = db
        self.lang = lang
        self.existing = existing
        self.scanned = False
        self.actions = []
        self.editing_action_index: int | None = None
        self._resize_pending = False
        self.result_guid = ""
        self.result_identity_type = WINBIO_ID_TYPE_GUID
        self.result_identity_value = ""
        self.result_sub_factor = 0x03
        title = tr(lang, "edit_finger") if existing else tr(lang, "add_finger")
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(WIZARD_WIDTH, WIZARD_COMPACT_HEIGHT)
        self.setStyleSheet(app_qss())

        self._capture_thread: QThread | None = None
        self._capture_worker: _CaptureWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title_bar = CleanWizardTitleBar(self, title)
        layout.addWidget(self.title_bar)

        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(16, 26, 16, 25)
        self.body_layout.setSpacing(0)
        self.stack = WizardPageStack()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.stack.setMinimumHeight(0)
        self.stack.setFixedHeight(self._stack_height_for_index(0))
        self.stack.addWidget(self._capture_step())
        self.stack.addWidget(self._actions_step())
        self.stack.addWidget(self._done_step())
        self.stack.currentChanged.connect(lambda _: self._sync_window_size())
        self.body_layout.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        nav.setContentsMargins(0, 18, 0, 0)
        self.back_btn = _wizard_button(tr(lang, "back"), "ghost", "back")
        self.next_btn = _wizard_button(tr(lang, "next"), "dark", "next")
        self.back_btn.setFixedSize(96, 36)
        self.next_btn.setFixedSize(83, 36)
        self.back_btn.clicked.connect(self.prev_step)
        self.next_btn.clicked.connect(self.next_step)
        nav.addWidget(self.back_btn)
        nav.addStretch()
        nav.addWidget(self.next_btn)
        self.body_layout.addLayout(nav)
        layout.addWidget(body, 1)

        if existing:
            self._load_existing(existing)
        self._sync_nav()
        self._sync_window_size()

    def _capture_step(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        card = QFrame()
        card.setProperty("role", "captureCard")
        card.setFixedHeight(254)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 22, 34, 22)
        card_layout.setSpacing(0)
        card_layout.addStretch()
        self.capture_icon = QLabel()
        self.capture_icon.setFixedSize(72, 72)
        self.capture_icon.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.capture_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.capture_icon.setPixmap(icon("icon_scan").pixmap(72, 72))
        self.capture_title = QLabel(tr(self.lang, "scan_prompt_title"))
        self.capture_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.capture_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{THEME.text};")
        self.capture_label = QLabel(tr(self.lang, "scan_prompt_body"))
        self.capture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.capture_label.setWordWrap(True)
        self.capture_label.setStyleSheet(f"color:{THEME.subtle};line-height:1.5;")
        self.capture_btn = _wizard_button(tr(self.lang, "scan_finger"), "primary")
        self.capture_btn.setFixedSize(max(142, self.capture_btn.sizeHint().width()), 36)
        self.capture_btn.clicked.connect(self.capture_finger)
        card_layout.addWidget(self.capture_icon, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addSpacing(20)
        card_layout.addWidget(self.capture_title)
        card_layout.addSpacing(12)
        card_layout.addWidget(self.capture_label)
        card_layout.addSpacing(20)
        card_layout.addWidget(self.capture_btn, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addStretch()
        layout.addSpacing(0)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _actions_step(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText(tr(self.lang, "finger_name_hint"))
        self.label_input.setFixedHeight(42)
        name_label = QLabel(tr(self.lang, "finger_name").upper())
        name_label.setProperty("role", "fieldLabel")
        layout.addWidget(name_label)
        layout.addWidget(self.label_input)
        layout.addSpacing(8)

        title = QLabel(tr(self.lang, "actions").upper())
        title.setProperty("role", "fieldLabel")
        layout.addWidget(title)

        self.action_card = QFrame()
        self.action_card.setProperty("role", "card")
        self.action_card.setFixedHeight(150)
        action_card_layout = QVBoxLayout(self.action_card)
        action_card_layout.setContentsMargins(16, 14, 16, 14)
        action_card_layout.setSpacing(8)
        self.action_type = ActionPicker(self.lang)
        self.action_type.setFixedHeight(42)
        self.action_type.currentIndexChanged.connect(self._sync_action_fields)

        self.action_value_label = QLabel(tr(self.lang, "data").upper())
        self.action_value_label.setProperty("role", "fieldLabel")
        self.action_value = QLineEdit()
        self.action_value.setPlaceholderText(tr(self.lang, "data_hint"))
        self.action_value.setFixedHeight(42)
        self.hotkey_value = HotkeyEdit()
        self.hotkey_value.setFixedHeight(42)
        self.action_value_stack = QStackedWidget()
        self.action_value_stack.setObjectName("actionValueStack")
        self.action_value_stack.setStyleSheet(
            "QStackedWidget#actionValueStack { background: transparent; border: 0; }"
        )
        self.action_value_stack.addWidget(self.action_value)
        self.action_value_stack.addWidget(self.hotkey_value)
        self.action_value_stack.setFixedHeight(42)

        self.browse = _wizard_button(tr(self.lang, "choose_file"), "secondary")
        self.browse.setFixedSize(max(WIZARD_BROWSE_BUTTON_WIDTH, self.browse.sizeHint().width()), 30)
        self.browse.clicked.connect(self.choose_file)

        self.add_action_btn = _wizard_button(tr(self.lang, "add_action"), "primary", "add")
        self.add_action_btn.setIconSize(QSize(14, 14))
        self.add_action_btn.setFixedSize(156, 30)
        self.add_action_btn.clicked.connect(self._add_action)

        action_type_label = QLabel(tr(self.lang, "action_type").upper())
        action_type_label.setProperty("role", "fieldLabel")
        action_card_layout.addWidget(action_type_label)
        action_card_layout.addWidget(self.action_type)
        action_card_layout.addWidget(self.action_value_label)
        action_card_layout.addWidget(self.action_value_stack)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        controls_row.addWidget(self.browse)
        controls_row.addWidget(self.add_action_btn)
        controls_row.addStretch()
        self.controls_row = controls_row
        action_card_layout.addSpacing(6)
        action_card_layout.addLayout(controls_row)
        layout.addWidget(self.action_card)

        actions_title = QLabel(tr(self.lang, "added_actions").upper())
        actions_title.setProperty("role", "fieldLabel")
        layout.addWidget(actions_title)

        self.actions_scroll = QScrollArea()
        self.actions_scroll.setWidgetResizable(True)
        self.actions_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.actions_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.actions_scroll.setFixedHeight(148)
        self.actions_container = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_container)
        self.actions_layout.setContentsMargins(0, 0, 8, 0)
        self.actions_layout.setSpacing(8)
        self.actions_scroll.setWidget(self.actions_container)
        layout.addWidget(self.actions_scroll)

        self._sync_action_fields()
        self._update_actions_display()
        return page

    def _done_step(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.done_card = QFrame()
        self.done_card.setProperty("role", "doneCard")
        self.done_card.setFixedHeight(208)
        card_layout = QVBoxLayout(self.done_card)
        card_layout.setContentsMargins(34, 20, 34, 20)
        card_layout.setSpacing(0)
        card_layout.addStretch()
        self.done_icon = QLabel()
        self.done_icon.setFixedSize(72, 72)
        self.done_icon.setPixmap(icon("icon_done").pixmap(72, 72))
        self.done_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_title = QLabel(tr(self.lang, "ready"))
        self.done_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_title.setStyleSheet(f"font-size:16px;font-weight:700;color:{THEME.text};")
        self.done_label = QLabel()
        self.done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.done_label.setWordWrap(True)
        self.done_label.setMaximumHeight(70)
        self.done_label.setStyleSheet(f"color:{THEME.subtle};")
        card_layout.addWidget(self.done_icon, 0, Qt.AlignmentFlag.AlignCenter)
        card_layout.addSpacing(20)
        card_layout.addWidget(self.done_title)
        card_layout.addSpacing(14)
        card_layout.addWidget(self.done_label)
        card_layout.addStretch()
        layout.addWidget(self.done_card)
        layout.addStretch(1)
        return page

    def capture_finger(self) -> None:
        if self._capture_thread is not None and self._capture_thread.isRunning():
            return

        self.capture_label.setText(tr(self.lang, "waiting_finger"))
        self.capture_btn.setEnabled(False)

        self._capture_thread = QThread(self)
        self._capture_worker = _CaptureWorker(self.lang)
        self._capture_worker.moveToThread(self._capture_thread)
        self._capture_thread.started.connect(self._capture_worker.run)
        self._capture_worker.captured.connect(self._on_capture_succeeded)
        self._capture_worker.failed.connect(self._on_capture_failed)
        self._capture_worker.captured.connect(self._capture_thread.quit)
        self._capture_worker.failed.connect(self._capture_thread.quit)
        self._capture_thread.finished.connect(self._cleanup_capture_thread)
        self._capture_thread.start()

    @pyqtSlot(dict)
    def _on_capture_succeeded(self, message: dict) -> None:
        self.result_guid = message.get("guid", "")
        self.result_identity_type = int(
            message.get("identity_type", WINBIO_ID_TYPE_GUID))
        self.result_identity_value = message.get(
            "identity_value") or self.result_guid
        self.result_sub_factor = int(message["sub_factor"])
        self.scanned = True
        finger_name = message.get("finger_name", "")
        if not self.label_input.text().strip():
            self.label_input.setText(finger_name)
        key = identity_key(self.result_identity_type,
                           self.result_identity_value, self.result_sub_factor)
        self.capture_title.setText(f"{tr(self.lang, 'recognized')}: {finger_name}")
        self.capture_label.setText(f"{tr(self.lang, 'key')}: {key}")
        self.capture_btn.setEnabled(True)
        self._sync_nav()

    @pyqtSlot(str, str)
    def _on_capture_failed(self, error_kind: str, message: str) -> None:
        self.scanned = False
        self.capture_title.setText(tr(self.lang, "scan_prompt_title"))
        self.capture_label.setText(message)
        self.capture_btn.setEnabled(True)
        self._sync_nav()

    def _cleanup_capture_thread(self) -> None:
        worker = self._capture_worker
        thread = self._capture_thread
        self._capture_worker = None
        self._capture_thread = None
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def closeEvent(self, event) -> None:
        if self._capture_worker is not None:
            self._capture_worker.cancel()
        if self._capture_thread is not None and self._capture_thread.isRunning():
            self._capture_thread.quit()
            self._capture_thread.wait(2000)
        super().closeEvent(event)

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr(self.lang, "choose_file"))
        if path:
            self.action_value.setText(path)

    def next_step(self) -> None:
        index = self.stack.currentIndex()
        if index == 0 and not self.scanned:
            self.capture_label.setText(tr(self.lang, "scan_first"))
            return
        if index == 1:
            if not self.actions:
                self.capture_label.setText(tr(self.lang, "add_action"))
                return
            self._save_binding()
        if index == self.stack.count() - 1:
            self.accept()
            return
        self.stack.setCurrentIndex(index + 1)
        self._sync_nav()

    def prev_step(self) -> None:
        if self.existing and self.stack.currentIndex() == 1:
            return
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._sync_nav()

    def _sync_window_size(self) -> None:
        height = self._window_height_for_index(self.stack.currentIndex())
        if hasattr(self, "body_layout"):
            self.body_layout.setContentsMargins(16, 18 if self.stack.currentIndex() == 1 else 26, 16, 25)
        self.stack.setFixedHeight(self._stack_height_for_index(self.stack.currentIndex()))
        self.layout().activate()
        if self.height() != height:
            self.setFixedSize(WIZARD_WIDTH, height)
            self.resize(WIZARD_WIDTH, height)

    def _stack_height_for_index(self, index: int) -> int:
        if index != 1:
            return 277
        return 410 if self._use_compact_action_page() else 493

    def _window_height_for_index(self, index: int) -> int:
        if index != 1:
            return WIZARD_COMPACT_HEIGHT
        return WIZARD_ACTION_EMPTY_HEIGHT if self._use_compact_action_page() else WIZARD_ACTION_HEIGHT

    def _use_compact_action_page(self) -> bool:
        return self._selected_action() in DATA_FREE_ACTIONS

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_window_size)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if not hasattr(self, "stack") or self._resize_pending:
            return
        expected = self._window_height_for_index(self.stack.currentIndex())
        if self.height() == expected:
            return
        self._resize_pending = True
        QTimer.singleShot(0, self._finish_resize_sync)

    def _finish_resize_sync(self) -> None:
        self._resize_pending = False
        self._sync_window_size()

    def _add_action(self) -> None:
        action = self._selected_action()
        if action == "hotkey":
            value = HotkeyEdit.normalize_hotkey(
                self.hotkey_value.text().strip())
            self.hotkey_value.setText(value)
        else:
            value = self.action_value.text().strip()
        if not value and action not in DATA_FREE_ACTIONS:
            return
        command_data = self._command_data(action, value)
        if self.editing_action_index is not None:
            previous_data = self.actions[self.editing_action_index].get("command_data") or {}
            command_data["delay_before"] = previous_data.get("delay_before", 0.0)
            command_data["delay_after"] = previous_data.get("delay_after", 0.0)
        try:
            command_data = validate_command_data(action, command_data)
        except ActionValidationError:
            return
        action_info = {
            "command_type": action,
            "command_data": command_data,
        }
        if self.editing_action_index is None:
            self.actions.append(action_info)
        else:
            self.actions[self.editing_action_index] = action_info
            self.editing_action_index = None
            self._set_add_button_mode()
        self.action_value.clear()
        self.hotkey_value.clear()
        self._update_actions_display()
        self._sync_window_size()

    def _delete_action(self, index: int) -> None:
        if 0 <= index < len(self.actions):
            self.actions.pop(index)
            if self.editing_action_index == index:
                self.editing_action_index = None
                self.action_value.clear()
                self.hotkey_value.clear()
                self._set_add_button_mode()
            elif self.editing_action_index is not None and self.editing_action_index > index:
                self.editing_action_index -= 1
            self._update_actions_display()
            self._sync_window_size()

    def _edit_action(self, index: int) -> None:
        if not 0 <= index < len(self.actions):
            return

        self.editing_action_index = index
        action_info = self.actions[index]
        command_type = action_info["command_type"]
        combo_index = self.action_type.findData(command_type)
        if combo_index >= 0:
            self.action_type.setCurrentIndex(combo_index)
        self._sync_action_fields()

        data = action_info.get("command_data") or {}
        definition = get_action_definition(command_type)
        value = data.get(definition.value_field, "") if definition.value_field else ""
        if command_type == "hotkey":
            self.hotkey_value.setText(str(value))
            self.hotkey_value.setFocus()
        else:
            self.action_value.setText(str(value))
            self.action_value.setFocus()
        self._set_update_button_mode()

    def _update_actions_display(self) -> None:
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        labels = action_labels(self.lang)
        if not self.actions:
            no_action_label = QLabel(tr(self.lang, "no_action"))
            no_action_label.setStyleSheet(f"color:{THEME.muted};font-style:italic;")
            self.actions_layout.addWidget(no_action_label)
        else:
            for i, action_info in enumerate(self.actions):
                self._add_action_row(i, action_info, labels)

        self.actions_layout.addStretch()

    def _add_action_row(self, index: int, action_info: dict, labels: dict) -> None:
        row = QFrame()
        row.setProperty("role", "actionRow")
        row.setFixedHeight(64)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 8, 14, 8)
        row_layout.setSpacing(10)

        cmd_type = action_info["command_type"]
        data = action_info["command_data"]
        summary = format_action_summary(
            cmd_type,
            data,
            labels.get(cmd_type, cmd_type),
        )

        number_label = QLabel(str(index + 1))
        number_label.setFixedWidth(20)
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setStyleSheet(f"color:{THEME.muted};font-size:13px;")

        text_block = QVBoxLayout()
        text_block.setSpacing(2)
        type_label = QLabel(labels.get(cmd_type, cmd_type))
        type_label.setMinimumWidth(0)
        type_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        type_label.setStyleSheet(f"font-weight:600;color:{THEME.text};")

        value_label = QLabel(summary)
        value_label.setWordWrap(True)
        value_label.setMinimumWidth(0)
        value_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        value_label.setMaximumHeight(30)
        value_label.setStyleSheet(f"color:{THEME.muted};font-family:Consolas,monospace;font-size:12px;")
        text_block.addWidget(type_label)
        text_block.addWidget(value_label)

        edit_btn = _wizard_button(tr(self.lang, "edit"), "actionSecondary", "edit")
        edit_btn.setFixedSize(max(124, edit_btn.sizeHint().width()), 28)
        edit_btn.clicked.connect(lambda: self._edit_action(index))

        delete_btn = _wizard_button("", "actionSecondary", "delete_action")
        delete_btn.setFixedSize(30, 30)
        delete_btn.clicked.connect(lambda: self._delete_action(index))

        row_layout.addWidget(number_label)
        row_layout.addLayout(text_block, 1)
        row_layout.addWidget(edit_btn)
        row_layout.addWidget(delete_btn)

        self.actions_layout.addWidget(row)

    def _save_binding(self) -> None:
        default_label = localized_finger_name(self.lang, self.result_sub_factor)
        label = self.label_input.text().strip() or default_label
        finger_id = self.db.save_finger(
            self.result_guid,
            self.result_sub_factor,
            label,
            identity_type=self.result_identity_type,
            identity_value=self.result_identity_value,
            finger_id=int(self.existing["id"]) if self.existing else None,
        )
        self.db.replace_commands(finger_id, self.actions)
        labels = action_labels(self.lang)
        if len(self.actions) == 1:
            action_names = labels.get(self.actions[0]["command_type"], self.actions[0]["command_type"])
        else:
            action_names = f"{len(self.actions)} {tr(self.lang, 'actions').lower()}"
        saved_text = tr(self.lang, "saved").format(label=label, action=action_names)
        saved_text = saved_text.replace(
            "<b>", f"<b style='color:{THEME.strong_text}'>"
        )
        self.done_label.setText(saved_text)

    def _load_existing(self, finger: dict) -> None:
        self.scanned = True
        self.result_guid = finger.get("guid", "")
        self.result_identity_type = int(
            finger.get("identity_type", WINBIO_ID_TYPE_GUID))
        self.result_identity_value = finger.get(
            "identity_value") or self.result_guid
        self.result_sub_factor = int(finger["sub_factor"])
        self.label_input.setText(finger.get("label", ""))

        for command in self.db.get_commands_by_finger_id(int(finger["id"])):
            self.actions.append({
                "command_type": command["command_type"],
                "command_data": command.get("command_data") or {},
                "enabled": command.get("enabled", True),
            })
        self.stack.setCurrentIndex(1)
        self._sync_action_fields()
        self._update_actions_display()

    def _selected_action(self) -> str:
        return str(self.action_type.currentData())

    def _command_data(self, action: str, value: str) -> dict:
        return build_command_data(action, value)

    def _sync_action_fields(self) -> None:
        action = self._selected_action()
        definition = get_action_definition(action)
        needs_data = definition.requires_value
        browse_active = action == "launch_app"
        self.action_value_label.setVisible(needs_data)
        self.action_value_stack.setVisible(needs_data)
        self.browse.setVisible(browse_active)
        self.add_action_btn.setFixedSize(
            self._add_button_width(browse_active),
            30,
        )
        self.action_card.setFixedHeight(204 if needs_data else 126)
        self._sync_window_size()
        self.controls_row.setAlignment(
            self.add_action_btn,
            Qt.AlignmentFlag.AlignLeft if browse_active else Qt.AlignmentFlag.AlignHCenter,
        )
        # Switch between regular text field and hotkey capture field.
        if definition.editor == "hotkey":
            self.action_value_stack.setCurrentIndex(1)
            self.hotkey_value.setFocus()
        else:
            self.action_value_stack.setCurrentIndex(0)

    def _set_add_button_mode(self) -> None:
        self.add_action_btn.setText(tr(self.lang, "add_action"))
        self.add_action_btn.setProperty("iconName", "add")
        self.add_action_btn.setIcon(icon("add"))
        self.add_action_btn.setIconSize(QSize(14, 14))
        self.add_action_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.add_action_btn.setFixedSize(
            self._add_button_width(self._selected_action() == "launch_app"),
            30,
        )
        self._sync_action_fields()

    def _set_update_button_mode(self) -> None:
        self.add_action_btn.setText(tr(self.lang, "update_action"))
        self.add_action_btn.setProperty("iconName", "check_version_white")
        self.add_action_btn.setIcon(icon("check_version_white"))
        self.add_action_btn.setIconSize(QSize(12, 12))
        self.add_action_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.add_action_btn.setFixedSize(
            self._add_button_width(self._selected_action() == "launch_app"),
            30,
        )
        self._sync_action_fields()

    def _add_button_width(self, browse_active: bool) -> int:
        if browse_active:
            return WIZARD_ACTION_BUTTON_WIDE - self.browse.width() - WIZARD_CONTROL_GAP
        return WIZARD_ACTION_BUTTON_WIDE

    def _sync_nav(self) -> None:
        self._sync_window_size()
        self.back_btn.setEnabled(
            self.stack.currentIndex() > 0
            and not (self.existing and self.stack.currentIndex() == 1)
        )
        self.next_btn.setEnabled(
            self.stack.currentIndex() != 0 or self.scanned)
        self.next_btn.setText(tr(self.lang, "done") if self.stack.currentIndex(
        ) == self.stack.count() - 1 else tr(self.lang, "next"))
        minimum_width = 100 if self.stack.currentIndex() == self.stack.count() - 1 else 83
        self.next_btn.setFixedWidth(max(minimum_width, self.next_btn.sizeHint().width()))
        if self.stack.currentIndex() == self.stack.count() - 1:
            next_icon = "done"
        elif not self.next_btn.isEnabled() and THEME.key != "light":
            next_icon = "inactive_next"
        else:
            next_icon = "next"
        self.next_btn.setProperty("iconName", next_icon)
        self.next_btn.setIcon(icon(next_icon))
        self.next_btn.setProperty("kind", "primary" if self.stack.currentIndex() == self.stack.count() - 1 else "dark")
        self.next_btn.style().unpolish(self.next_btn)
        self.next_btn.style().polish(self.next_btn)
