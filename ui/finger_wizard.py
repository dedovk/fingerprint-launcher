"""Dialog for binding a recognized finger to an action."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
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
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QKeySequence

import time

from core.database import Database
from core.winbio import (
    FINGER_NAMES,
    WINBIO_ID_TYPE_GUID,
    WINBIO_POOL_PRIVATE,
    WINBIO_POOL_SYSTEM,
    WINBIO_E_NO_MATCH,
    WINBIO_E_UNKNOWN_ID,
    S_OK,
    WinBioSession,
    enumerate_biometric_units,
    identity_key,
)
from ui.i18n import action_labels, tr


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
            if not self.capture_only:
                # Win-based system shortcuts (e.g. Win+R) are reserved by Windows.
                # Users can type them manually into the field.
                return
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
                    "finger_name": result.finger_name,
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
        self.result_guid = ""
        self.result_identity_type = WINBIO_ID_TYPE_GUID
        self.result_identity_value = ""
        self.result_sub_factor = 0x03
        self.setWindowTitle(tr(lang, "edit_finger")
                            if existing else tr(lang, "add_finger"))
        self.resize(700, 550)
        self.setMinimumSize(650, 450)

        self._capture_thread: QThread | None = None
        self._capture_worker: _CaptureWorker | None = None

        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._capture_step())
        self.stack.addWidget(self._actions_step())
        self.stack.addWidget(self._done_step())
        layout.addWidget(self.stack)

        nav = QHBoxLayout()
        self.back_btn = QPushButton(tr(lang, "back"))
        self.next_btn = QPushButton(tr(lang, "next"))
        self.back_btn.setMinimumWidth(96)
        self.next_btn.setMinimumWidth(96)
        self.back_btn.clicked.connect(self.prev_step)
        self.next_btn.clicked.connect(self.next_step)
        nav.addStretch()
        nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn)
        layout.addLayout(nav)

        if existing:
            self._load_existing(existing)
        self._sync_nav()

    def _capture_step(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        self.capture_label = QLabel(tr(self.lang, "scan_prompt"))
        self.capture_label.setObjectName("captureMessage")
        self.capture_label.setWordWrap(True)
        self.capture_label.setMinimumHeight(80)
        self.capture_btn = QPushButton(tr(self.lang, "scan_finger"))
        self.capture_btn.setMinimumHeight(40)
        self.capture_btn.clicked.connect(self.capture_finger)
        layout.addWidget(self.capture_label)
        layout.addWidget(self.capture_btn)
        layout.addStretch()
        return page

    def _actions_step(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText(tr(self.lang, "finger_name_hint"))
        self.label_input.setMinimumHeight(32)
        label_layout = QFormLayout()
        label_layout.addRow(tr(self.lang, "finger_name"), self.label_input)
        layout.addLayout(label_layout)

        title = QLabel("<b>" + tr(self.lang, "actions") + ":</b>")
        layout.addWidget(title)

        self.action_type = QComboBox()
        self.action_type.setMinimumHeight(32)
        for command_type, label in action_labels(self.lang).items():
            self.action_type.addItem(label, command_type)
        self.action_type.currentIndexChanged.connect(self._sync_action_fields)

        self.action_value_label = QLabel(tr(self.lang, "data"))
        self.action_value = QLineEdit()
        self.action_value.setPlaceholderText(tr(self.lang, "data_hint"))
        self.action_value.setMinimumHeight(32)
        self.hotkey_value = HotkeyEdit()
        self.hotkey_value.setMinimumHeight(32)
        self.action_value_stack = QStackedWidget()
        self.action_value_stack.addWidget(self.action_value)
        self.action_value_stack.addWidget(self.hotkey_value)
        self.action_value_stack.setMaximumHeight(40)

        self.browse = QPushButton(tr(self.lang, "choose_file"))
        self.browse.setMinimumHeight(32)
        self.browse.setMinimumWidth(140)
        self.browse.clicked.connect(self.choose_file)

        self.add_action_btn = QPushButton(tr(self.lang, "add_action"))
        self.add_action_btn.setMinimumHeight(32)
        self.add_action_btn.setMinimumWidth(140)
        self.add_action_btn.clicked.connect(self._add_action)

        action_form = QFormLayout()
        action_form.setSpacing(8)
        action_form.addRow(tr(self.lang, "action_type"), self.action_type)
        action_form.addRow(self.action_value_label, self.action_value_stack)
        layout.addLayout(action_form)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        controls_row.addWidget(self.browse)
        controls_row.addWidget(self.add_action_btn)
        controls_row.addStretch()
        layout.addLayout(controls_row)

        actions_title = QLabel(
            "<b>" + tr(self.lang, "added_actions") + ":</b>")
        layout.addWidget(actions_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)
        self.actions_container = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_container)
        self.actions_layout.setSpacing(6)
        scroll.setWidget(self.actions_container)
        layout.addWidget(scroll)

        self._sync_action_fields()
        self._update_actions_display()
        return page

    def _done_step(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        self.done_label = QLabel()
        self.done_label.setObjectName("captureMessage")
        self.done_label.setWordWrap(True)
        self.done_label.setMinimumHeight(80)
        layout.addWidget(self.done_label)
        layout.addStretch()
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
        self.capture_label.setText(
            f"{tr(self.lang, 'recognized')}: {finger_name}\n{tr(self.lang, 'key')}: {key}")
        self.capture_btn.setEnabled(True)
        self._sync_nav()

    @pyqtSlot(str, str)
    def _on_capture_failed(self, error_kind: str, message: str) -> None:
        self.scanned = False
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

    def _add_action(self) -> None:
        action = self._selected_action()
        if action == "hotkey":
            value = HotkeyEdit.normalize_hotkey(
                self.hotkey_value.text().strip())
            self.hotkey_value.setText(value)
        else:
            value = self.action_value.text().strip()
        if not value and action != "lock_screen":
            return
        action_info = {
            "command_type": action,
            "command_data": self._command_data(action, value),
        }
        if self.editing_action_index is None:
            self.actions.append(action_info)
        else:
            self.actions[self.editing_action_index] = action_info
            self.editing_action_index = None
            self.add_action_btn.setText(tr(self.lang, "add_action"))
        self.action_value.clear()
        self.hotkey_value.clear()
        self._update_actions_display()

    def _delete_action(self, index: int) -> None:
        if 0 <= index < len(self.actions):
            self.actions.pop(index)
            if self.editing_action_index == index:
                self.editing_action_index = None
                self.action_value.clear()
                self.hotkey_value.clear()
                self.add_action_btn.setText(tr(self.lang, "add_action"))
            elif self.editing_action_index is not None and self.editing_action_index > index:
                self.editing_action_index -= 1
            self._update_actions_display()

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
        value = (
            data.get("path")
            or data.get("url")
            or data.get("keys")
            or data.get("cmd")
            or ""
        )
        if command_type == "hotkey":
            self.hotkey_value.setText(str(value))
            self.hotkey_value.setFocus()
        else:
            self.action_value.setText(str(value))
            self.action_value.setFocus()
        self.add_action_btn.setText("Update action")

    def _update_actions_display(self) -> None:
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        labels = action_labels(self.lang)
        if not self.actions:
            no_action_label = QLabel(tr(self.lang, "no_action"))
            no_action_label.setStyleSheet("color: #999; font-style: italic;")
            self.actions_layout.addWidget(no_action_label)
        else:
            for i, action_info in enumerate(self.actions):
                self._add_action_row(i, action_info, labels)

        self.actions_layout.addStretch()

    def _add_action_row(self, index: int, action_info: dict, labels: dict) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setSpacing(8)

        cmd_type = action_info["command_type"]
        data = action_info["command_data"]
        summary = data.get("path") or data.get("url") or data.get("keys") or data.get(
            "cmd") or ("LockWorkStation" if cmd_type == "lock_screen" else "")

        label_text = f"{index + 1}. {labels.get(cmd_type, cmd_type)}"
        type_label = QLabel(label_text)
        type_label.setMinimumWidth(120)
        type_label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        type_label.setStyleSheet("font-weight: 600;")

        value_label = QLabel(summary)
        value_label.setWordWrap(True)
        value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        value_label.setStyleSheet("color: #666;")

        edit_btn = QPushButton(tr(self.lang, "edit"))
        edit_btn.setMinimumWidth(max(72, edit_btn.sizeHint().width()))
        edit_btn.setMinimumHeight(28)
        edit_btn.clicked.connect(lambda: self._edit_action(index))

        delete_btn = QPushButton("X")
        delete_btn.setMaximumWidth(32)
        delete_btn.setMinimumHeight(28)
        delete_btn.setStyleSheet(
            "padding: 2px; font-weight: bold; color: #dc2626;")
        delete_btn.clicked.connect(lambda: self._delete_action(index))

        row_layout.addWidget(type_label)
        row_layout.addWidget(value_label, 1)
        row_layout.addWidget(edit_btn)
        row_layout.addWidget(delete_btn)

        self.actions_layout.addWidget(row)

    def _save_binding(self) -> None:
        default_label = FINGER_NAMES.get(self.result_sub_factor, "Unknown")
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
        action_names = ", ".join(labels.get(
            a["command_type"], a["command_type"]) for a in self.actions)
        self.done_label.setText(tr(self.lang, "saved").format(
            label=label, action=action_names))

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
        if action == "launch_app":
            return {"path": value, "args": ""}
        if action == "open_url":
            return {"url": value}
        if action == "hotkey":
            return {"keys": value}
        if action == "shell":
            return {"cmd": value, "hidden": True}
        return {}

    def _sync_action_fields(self) -> None:
        action = self._selected_action()
        needs_data = action != "lock_screen"
        self.action_value_label.setVisible(needs_data)
        self.action_value_stack.setVisible(needs_data)
        self.browse.setVisible(action == "launch_app")
        # Switch between regular text field and hotkey capture field.
        if action == "hotkey":
            self.action_value_stack.setCurrentIndex(1)
            self.hotkey_value.setFocus()
        else:
            self.action_value_stack.setCurrentIndex(0)

    def _sync_nav(self) -> None:
        self.back_btn.setEnabled(
            self.stack.currentIndex() > 0
            and not (self.existing and self.stack.currentIndex() == 1)
        )
        self.next_btn.setEnabled(
            self.stack.currentIndex() != 0 or self.scanned)
        self.next_btn.setText(tr(self.lang, "done") if self.stack.currentIndex(
        ) == self.stack.count() - 1 else tr(self.lang, "next"))
