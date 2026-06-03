"""Main settings window."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.database import Database
from services.autostart import remove_user_autostart, setup_user_autostart
from ui.finger_wizard import FingerWizard, HotkeyEdit
from ui.i18n import LANGUAGES, action_labels, tr
from ui.scan_prompt import ScanPrompt
from ui.triggered_scan import TriggeredFingerprintScan


APP_VERSION = "1.0.0"

BASE_QSS = """
    QPushButton { border-radius: 7px; padding: 3px 7px; min-height: 20px; font-size: 12px; }
    QComboBox { padding: 4px 26px 4px 8px; min-height: 20px; }
    QComboBox::drop-down { border: 0; background: transparent; width: 22px; }
    QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #333333; width: 0; height: 0; margin-right: 8px; }
"""

THEMES_DICT = {
    "light": BASE_QSS + """
        QWidget { background: #f8fafc; color: #111827; font-size: 13px; }
        QGroupBox { border: 1px solid #d8dee8; border-radius: 8px; margin-top: 14px; padding: 13px 11px 11px; font-weight: 600; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; background: #f8fafc; }
        QTabWidget::pane { border: 1px solid #d8dee8; border-radius: 8px; top: -1px; background: #ffffff; }
        QTabBar::tab { background: #eef2f7; color: #111827; padding: 7px 14px; border: 1px solid #d8dee8; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px; }
        QTabBar::tab:selected { background: #ffffff; color: #0f172a; }
        QPushButton { background: #ffffff; color: #111827; border: 1px solid #cbd5e1; }
        QPushButton:hover { background: #f1f5f9; }
        QLineEdit, QComboBox, QTableWidget { background: #ffffff; color: #111827; border: 1px solid #cbd5e1; border-radius: 7px; }
        QHeaderView::section { background: #eef2f7; color: #111827; border: none; border-right: 1px solid #d8dee8; padding: 6px; font-weight: 600; }
        QLabel#captureMessage, QLabel#statusMessage { background: #ffffff; border: 1px solid #d8dee8; border-radius: 8px; padding: 10px; }
        QComboBox::down-arrow { border-top-color: #111827; }
    """,
    "dark": BASE_QSS + """
        QWidget { background: #111827; color: #f9fafb; font-size: 13px; }
        QGroupBox { border: 1px solid #374151; border-radius: 8px; margin-top: 14px; padding: 13px 11px 11px; font-weight: 600; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; background: #111827; }
        QTabWidget::pane { border: 1px solid #374151; border-radius: 8px; top: -1px; background: #172033; }
        QTabBar::tab { background: #1f2937; color: #d1d5db; padding: 7px 14px; border: 1px solid #374151; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px; }
        QTabBar::tab:selected { background: #172033; color: #ffffff; }
        QPushButton { background: #243044; color: #f9fafb; border: 1px solid #4b5563; }
        QPushButton:hover { background: #334155; }
        QLineEdit, QComboBox, QTableWidget { background: #172033; color: #f9fafb; border: 1px solid #4b5563; border-radius: 7px; }
        QHeaderView::section { background: #1f2937; color: #f9fafb; border: none; border-right: 1px solid #374151; padding: 6px; font-weight: 600; }
        QLabel#captureMessage, QLabel#statusMessage { background: #172033; border: 1px solid #374151; border-radius: 8px; padding: 10px; }
    """,
    "gray": BASE_QSS + """
        QWidget { background: #e5e7eb; color: #111827; font-size: 13px; }
        QGroupBox { border: 1px solid #9ca3af; border-radius: 8px; margin-top: 14px; padding: 13px 11px 11px; font-weight: 600; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; background: #e5e7eb; }
        QTabWidget::pane { border: 1px solid #9ca3af; border-radius: 8px; top: -1px; background: #f3f4f6; }
        QTabBar::tab { background: #d1d5db; color: #111827; padding: 7px 14px; border: 1px solid #9ca3af; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px; }
        QTabBar::tab:selected { background: #f3f4f6; color: #111827; }
        QPushButton { background: #f9fafb; color: #111827; border: 1px solid #9ca3af; }
        QPushButton:hover { background: #ffffff; }
        QLineEdit, QComboBox, QTableWidget { background: #f9fafb; color: #111827; border: 1px solid #9ca3af; border-radius: 7px; }
        QHeaderView::section { background: #d1d5db; color: #111827; border: none; border-right: 1px solid #9ca3af; padding: 6px; font-weight: 600; }
        QLabel#captureMessage, QLabel#statusMessage { background: #f9fafb; border: 1px solid #9ca3af; border-radius: 8px; padding: 10px; }
        QComboBox::down-arrow { border-top-color: #111827; }
    """,
}


class MainWindow(QMainWindow):
    language_changed = pyqtSignal(str)
    activation_requested = pyqtSignal()

    def __init__(self, db: Database | None = None) -> None:
        super().__init__()
        self.db = db or Database()
        self.lang = self.db.get_setting("language", "uk") or "uk"
        self.scan_thread: QThread | None = None
        self.scan_worker: TriggeredFingerprintScan | None = None
        self.hotkey_handle = None
        self.scan_prompt = ScanPrompt(self.lang)
        self.allow_close = False
        self.activation_requested.connect(self.start_triggered_scan)

        self.setWindowTitle("FingerprintLauncher")
        self.resize(900, 560)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._fingers_tab(), "")
        self.tabs.addTab(self._status_tab(), "")
        self.tabs.addTab(self._settings_tab(), "")
        self.setCentralWidget(self.tabs)

        self.apply_theme(self.db.get_setting("theme", "light") or "light")
        self.retranslate()
        self.refresh_fingers()
        self.register_activation_hotkey()

    def _fingers_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.fingers_table = QTableWidget(0, 4)
        self.fingers_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.fingers_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self.fingers_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.fingers_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents)
        self.fingers_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.fingers_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.fingers_table.setSortingEnabled(True)
        layout.addWidget(self.fingers_table)

        buttons = QHBoxLayout()
        style = self.style()
        self.add_btn = QPushButton()
        self.edit_btn = QPushButton()
        self.delete_btn = QPushButton()
        self.add_btn.setIcon(style.standardIcon(
            QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.edit_btn.setIcon(style.standardIcon(
            QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.delete_btn.setIcon(style.standardIcon(
            QStyle.StandardPixmap.SP_TrashIcon))
        self.add_btn.clicked.connect(self.add_finger)
        self.edit_btn.clicked.connect(self.edit_selected_finger)
        self.delete_btn.clicked.connect(self.delete_selected_finger)
        for btn in (self.add_btn, self.edit_btn, self.delete_btn):
            btn.setMinimumWidth(130)
        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.edit_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _status_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.status_group = QGroupBox()
        status_layout = QVBoxLayout(self.status_group)
        self.monitor_status = QLabel()
        self.last_activity = QLabel()
        self.last_activity.setObjectName("statusMessage")
        status_layout.addWidget(self.monitor_status)
        status_layout.addWidget(self.last_activity)
        layout.addWidget(self.status_group)
        layout.addStretch()
        return page

    def _settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.app_group = QGroupBox()
        app_layout = QVBoxLayout(self.app_group)
        self.autostart = QCheckBox()
        self.autostart.setChecked(self.db.get_setting("autostart", "1") == "1")
        self.autostart.stateChanged.connect(self.toggle_autostart)
        app_layout.addWidget(self.autostart)

        self.activation_group = QGroupBox()
        activation_layout = QGridLayout(self.activation_group)
        self.activation_hotkey_label = QLabel()
        self.activation_hotkey_input = HotkeyEdit(capture_only=True, require_modifier=True)
        self.activation_hotkey_input.setText(self.activation_hotkey())
        self.activation_hotkey_save = QPushButton()
        self.activation_hotkey_save.clicked.connect(self.save_activation_hotkey)
        activation_layout.addWidget(self.activation_hotkey_label, 0, 0)
        activation_layout.addWidget(self.activation_hotkey_input, 0, 1)
        activation_layout.addWidget(self.activation_hotkey_save, 0, 2)

        self.appearance_group = QGroupBox()
        appearance_layout = QGridLayout(self.appearance_group)
        self.theme_label = QLabel()
        self.theme_combo = QComboBox()
        self._theme_map = {"light": tr(self.lang, "light"), "dark": tr(
            self.lang, "dark"), "gray": tr(self.lang, "gray")}
        self.theme_combo.addItems(self._theme_map.values())
        current_theme = self.db.get_setting("theme", "light") or "light"
        self.theme_combo.setCurrentText(self._theme_map.get(
            current_theme, self._theme_map["light"]))
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(self.lang)))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        self.version_label = QLabel()
        self.version_value = QLabel(APP_VERSION)
        appearance_layout.addWidget(self.theme_label, 0, 0)
        appearance_layout.addWidget(self.theme_combo, 0, 1)
        appearance_layout.addWidget(self.language_label, 1, 0)
        appearance_layout.addWidget(self.language_combo, 1, 1)
        appearance_layout.addWidget(self.version_label, 2, 0)
        appearance_layout.addWidget(self.version_value, 2, 1)

        layout.addWidget(self.app_group)
        layout.addWidget(self.activation_group)
        layout.addWidget(self.appearance_group)
        layout.addStretch()
        return page

    def retranslate(self) -> None:
        self.tabs.setTabText(0, tr(self.lang, "my_fingers"))
        self.tabs.setTabText(1, tr(self.lang, "status"))
        self.tabs.setTabText(2, tr(self.lang, "settings"))
        self.fingers_table.setHorizontalHeaderLabels([tr(self.lang, "finger"), tr(
            self.lang, "action"), tr(self.lang, "command"), tr(self.lang, "activity")])
        self.add_btn.setText(tr(self.lang, "add"))
        self.edit_btn.setText(tr(self.lang, "edit"))
        self.delete_btn.setText(tr(self.lang, "delete"))
        self.status_group.setTitle(tr(self.lang, "status"))
        self.app_group.setTitle(tr(self.lang, "startup"))
        self.activation_group.setTitle(tr(self.lang, "activation"))
        self.appearance_group.setTitle(tr(self.lang, "appearance"))
        self.autostart.setText(tr(self.lang, "autostart"))
        self.activation_hotkey_label.setText(tr(self.lang, "activation_hotkey"))
        self.activation_hotkey_save.setText(tr(self.lang, "save"))
        self.theme_label.setText(tr(self.lang, "theme"))
        self.language_label.setText(tr(self.lang, "language"))
        self.version_label.setText(tr(self.lang, "version"))
        self._theme_map = {"light": tr(self.lang, "light"), "dark": tr(
            self.lang, "dark"), "gray": tr(self.lang, "gray")}
        current_theme = self.db.get_setting("theme", "light") or "light"
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItems(self._theme_map.values())
        self.theme_combo.setCurrentText(self._theme_map.get(
            current_theme, self._theme_map["light"]))
        self.theme_combo.blockSignals(False)
        self.refresh_status()
        if not self.last_activity.text() or self.last_activity.text() == tr(self.lang, "last_activity_none"):
            self.last_activity.setText(tr(self.lang, "last_activity_none"))
        self.refresh_fingers()

    def refresh_fingers(self) -> None:
        self.fingers_table.setSortingEnabled(False)
        self.fingers_table.setRowCount(0)
        labels = action_labels(self.lang)

        # Group fingers and their commands
        fingers_dict = {}
        for item in self.db.list_fingers():
            finger_id = item["id"]
            if finger_id not in fingers_dict:
                fingers_dict[finger_id] = {
                    "id": finger_id,
                    "label": item["label"],
                    "commands": [],
                }
            if item.get("command_type"):
                fingers_dict[finger_id]["commands"].append({
                    "command_id": item.get("command_id"),
                    "command_type": item.get("command_type"),
                    "command_data": item.get("command_data"),
                    "enabled": bool(item.get("enabled", 1)),
                })

        # Add one row per finger
        for finger in fingers_dict.values():
            row = self.fingers_table.rowCount()
            self.fingers_table.insertRow(row)

            # Column 0: Finger name
            finger_item = QTableWidgetItem(str(finger["label"]))
            finger_item.setData(Qt.ItemDataRole.UserRole, finger["id"])
            self.fingers_table.setItem(row, 0, finger_item)

            # Column 1: Action types
            if finger["commands"]:
                action_types = ", ".join(
                    labels.get(cmd["command_type"], cmd["command_type"])
                    for cmd in finger["commands"]
                )
            else:
                action_types = tr(self.lang, "no_action")
            self.fingers_table.setItem(row, 1, QTableWidgetItem(action_types))

            # Column 2: Command summary
            summaries = []
            for cmd in finger["commands"]:
                data = cmd.get("command_data") or {}
                summary = (data.get("path") or data.get("url") or
                           data.get("keys") or data.get("cmd") or
                           ("LockWorkStation" if cmd["command_type"] == "lock_screen" else ""))
                if summary:
                    summaries.append(summary)
            self.fingers_table.setItem(
                row, 2, QTableWidgetItem(" | ".join(summaries)))

            # Column 3: Status toggle (use first command for state)
            first_cmd = finger["commands"][0] if finger["commands"] else None
            self.fingers_table.setCellWidget(
                row, 3, self._enabled_switch(first_cmd.get("command_id") if first_cmd else None,
                                             first_cmd.get("enabled") if first_cmd else False))

        self.fingers_table.setSortingEnabled(True)
        self.fingers_table.sortItems(0, Qt.SortOrder.AscendingOrder)

    def _enabled_switch(self, command_id: int | None, enabled: bool) -> QWidget:
        wrapper = QFrame()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(6, 0, 6, 0)
        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.setEnabled(command_id is not None)
        checkbox.setProperty("command_id", command_id)
        checkbox.stateChanged.connect(self.toggle_command_enabled)
        self._style_enabled_switch(checkbox, enabled)
        layout.addWidget(checkbox)
        return wrapper

    def _style_enabled_switch(self, checkbox: QCheckBox, enabled: bool) -> None:
        color = "#16a34a" if enabled else "#dc2626"
        checkbox.setText(tr(self.lang, "enabled")
                         if enabled else tr(self.lang, "disabled"))
        checkbox.setStyleSheet(
            f"QCheckBox {{ color: {color}; font-weight: 600; }}")

    def toggle_command_enabled(self, state: int) -> None:
        checkbox = self.sender()
        command_id = checkbox.property("command_id")
        if command_id is None:
            return
        enabled = state == Qt.CheckState.Checked.value
        self.db.set_command_enabled(int(command_id), enabled)
        self._style_enabled_switch(checkbox, enabled)

    def refresh_status(self) -> None:
        self.monitor_status.setText(
            tr(self.lang, "hotkey_status").format(hotkey=self.activation_hotkey())
        )

    def add_finger(self) -> None:
        wizard = FingerWizard(self.db, self, lang=self.lang)
        if wizard.exec():
            self.refresh_fingers()

    def edit_selected_finger(self) -> None:
        finger = self._selected_finger()
        if not finger:
            return
        wizard = FingerWizard(self.db, self, existing=finger, lang=self.lang)
        if wizard.exec():
            self.refresh_fingers()

    def delete_selected_finger(self) -> None:
        finger = self._selected_finger()
        if finger:
            self.db.delete_finger(int(finger["id"]))
            self.refresh_fingers()

    def _selected_finger(self) -> dict | None:
        selected = self.fingers_table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.fingers_table.item(selected[0].row(), 0)
        return self._finger_by_id(int(item.data(Qt.ItemDataRole.UserRole))) if item else None

    def _finger_by_id(self, finger_id: int) -> dict | None:
        return next((finger for finger in self.db.list_fingers() if int(finger["id"]) == finger_id), None)

    def activation_hotkey(self) -> str:
        hotkey = HotkeyEdit.normalize_hotkey(
            self.db.get_setting("activation_hotkey", "ctrl+alt+f") or "ctrl+alt+f"
        )
        if not self._is_valid_activation_hotkey(hotkey):
            return "ctrl+alt+f"
        return hotkey

    def _is_valid_activation_hotkey(self, hotkey: str) -> bool:
        parts = set(HotkeyEdit.normalize_hotkey(hotkey).split("+"))
        primary_modifiers = {"ctrl", "alt", "windows"}
        return bool(parts & primary_modifiers) and len(parts - primary_modifiers - {"shift"}) >= 1

    def save_activation_hotkey(self) -> None:
        hotkey = HotkeyEdit.normalize_hotkey(self.activation_hotkey_input.text().strip())
        if not self._is_valid_activation_hotkey(hotkey):
            self.activation_hotkey_input.setText(self.activation_hotkey())
            return
        self.activation_hotkey_input.setText(hotkey)
        self.db.set_setting("activation_hotkey", hotkey)
        self.register_activation_hotkey()
        self.refresh_status()

    def register_activation_hotkey(self) -> None:
        self.unregister_activation_hotkey()
        hotkey = self.activation_hotkey()
        try:
            import keyboard

            self.hotkey_handle = keyboard.add_hotkey(
                hotkey,
                lambda: self.activation_requested.emit(),
                suppress=False,
            )
        except Exception as exc:
            self.hotkey_handle = None
            self.last_activity.setText(str(exc))

    def unregister_activation_hotkey(self) -> None:
        if self.hotkey_handle is None:
            return
        try:
            import keyboard

            keyboard.remove_hotkey(self.hotkey_handle)
        except Exception:
            pass
        self.hotkey_handle = None

    def start_triggered_scan(self) -> None:
        if self.scan_thread is not None and self.scan_thread.isRunning():
            return

        self.scan_prompt.show_prompt(self.lang)
        self.last_activity.setText(tr(self.lang, "scan_popup_waiting"))

        self.scan_thread = QThread(self)
        self.scan_worker = TriggeredFingerprintScan(self.db.path, self.lang)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.activity.connect(self.on_scan_activity)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self._scan_thread_finished)
        self.scan_thread.start()

    def _scan_thread_finished(self) -> None:
        worker = self.scan_worker
        thread = self.scan_thread
        self.scan_worker = None
        self.scan_thread = None
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def on_scan_activity(self, message: str) -> None:
        self.last_activity.setText(message)
        self.scan_prompt.set_result(message)
        self.scan_prompt.close_later()

    def on_scan_error(self, message: str) -> None:
        self.last_activity.setText(message)
        self.scan_prompt.set_result(message)
        self.scan_prompt.close_later(2400)

    def toggle_autostart(self, state: int) -> None:
        import sys
        enabled = state == Qt.CheckState.Checked.value
        self.db.set_setting("autostart", "1" if enabled else "0")
        setup_user_autostart(sys.executable) if enabled else remove_user_autostart()

    def change_theme(self, theme_display_name: str) -> None:
        theme_key = next((k for k, v in self._theme_map.items()
                         if v == theme_display_name), "light")
        self.db.set_setting("theme", theme_key)
        self.apply_theme(theme_key)

    def change_language(self) -> None:
        self.lang = str(self.language_combo.currentData())
        self.db.set_setting("language", self.lang)
        self.retranslate()
        self.language_changed.emit(self.lang)

    def apply_theme(self, theme_key: str) -> None:
        self.setStyleSheet(THEMES_DICT.get(theme_key, THEMES_DICT["light"]))

    def show_settings(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def shutdown(self) -> None:
        self.allow_close = True
        self.unregister_activation_hotkey()
        if self.scan_worker is not None:
            self.scan_worker.cancel()
        self.close()

    def closeEvent(self, event) -> None:
        if self.allow_close:
            self.unregister_activation_hotkey()
            if self.scan_worker is not None:
                self.scan_worker.cancel()
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()
