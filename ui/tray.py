"""System tray integration."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from ui.i18n import tr
from ui.theme import THEME, configure_theme, icon_path
from core.time_utils import format_countdown


class FingerprintTray(QSystemTrayIcon):
    pause_toggled = pyqtSignal(bool)

    def __init__(self, icon: QIcon, parent=None, lang: str = "uk") -> None:
        super().__init__(icon, parent)
        self.lang = lang
        self.title_action = QAction("FingerprintLauncher")
        self.title_action.setEnabled(False)
        self.settings_action = QAction()
        self.pause_action = QAction()
        self.pause_action.setCheckable(True)
        self.pause_action.triggered.connect(self.pause_toggled.emit)
        self.timers_menu = QMenu()
        self._timer_manager = None
        self._timer_snapshots: list[dict] = []
        self._timer_actions: dict[str, QAction] = {}
        self.quit_action = QAction()
        self._build_menu()
        self.set_language(lang)

    def _build_menu(self) -> None:
        self.menu = QMenu()
        self.set_theme(THEME.key)
        self.menu.addAction(self.title_action)
        self.menu.addSeparator()
        self.menu.addAction(self.settings_action)
        self.menu.addAction(self.pause_action)
        self.menu.addMenu(self.timers_menu)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.setContextMenu(self.menu)

    def set_theme(self, theme_key: str) -> None:
        configure_theme(theme_key)
        checked_icon = icon_path("checkbox_checked").replace("\\", "/")
        menu_background = THEME.popup_surface if THEME.is_gradient else THEME.surface
        stylesheet = f"""
            QMenu {{
                background: {menu_background};
                color: {THEME.text};
                border: 1px solid {THEME.border};
                border-radius: 10px;
                padding: 6px;
                font-family: "Segoe UI";
                font-size: 13px;
            }}
            QMenu::item {{
                padding: 7px 28px 7px 12px;
                border-radius: 7px;
            }}
            QMenu::item:selected {{
                background: {THEME.selected_bg};
                color: {THEME.text};
            }}
            QMenu::item:disabled {{
                color: {THEME.primary};
                font-weight: 600;
            }}
            QMenu::separator {{
                height: 1px;
                background: {THEME.border};
                margin: 6px 4px;
            }}
            QMenu::indicator {{
                width: 12px;
                height: 12px;
                border: 1px solid {THEME.border};
                border-radius: 3px;
                background: {THEME.action_row_bg};
            }}
            QMenu::indicator:checked {{
                image: url("{checked_icon}");
                border-color: {THEME.primary};
                background: {THEME.primary};
            }}
            """
        self.menu.setStyleSheet(stylesheet)
        self.timers_menu.setStyleSheet(stylesheet)

    def set_language(self, lang: str) -> None:
        self.lang = lang
        self.settings_action.setText(tr(lang, "settings_menu"))
        self.pause_action.setText(
            tr(lang, "resume_hotkey") if self.pause_action.isChecked()
            else tr(lang, "pause_hotkey")
        )
        self.quit_action.setText(tr(lang, "quit"))
        self._rebuild_timers_menu()

    def set_paused(self, paused: bool) -> None:
        self.pause_action.blockSignals(True)
        self.pause_action.setChecked(bool(paused))
        self.pause_action.blockSignals(False)
        self.pause_action.setText(
            tr(self.lang, "resume_hotkey") if paused else tr(self.lang, "pause_hotkey")
        )

    def bind_timer_manager(self, manager) -> None:
        self._timer_manager = manager
        manager.timers_changed.connect(self._set_timer_snapshots)
        manager.timer_finished.connect(self._show_timer_finished)
        self._set_timer_snapshots(manager.snapshots())

    def _set_timer_snapshots(self, timers: list[dict]) -> None:
        previous_ids = set(self._timer_actions)
        self._timer_snapshots = list(timers)
        current_ids = {str(timer["timer_id"]) for timer in self._timer_snapshots}
        if previous_ids != current_ids:
            self._rebuild_timers_menu()
            return
        self.timers_menu.setTitle(
            f"{tr(self.lang, 'active_timers')} ({len(self._timer_snapshots)})"
        )
        for timer in self._timer_snapshots:
            action = self._timer_actions.get(str(timer["timer_id"]))
            if action is not None:
                action.setText(self._timer_action_text(timer))

    def _rebuild_timers_menu(self) -> None:
        self.timers_menu.clear()
        self._timer_actions.clear()
        count = len(self._timer_snapshots)
        self.timers_menu.setTitle(f"{tr(self.lang, 'active_timers')} ({count})")
        if not self._timer_snapshots:
            empty = self.timers_menu.addAction(tr(self.lang, "no_active_timers"))
            empty.setEnabled(False)
            return

        for timer in self._timer_snapshots:
            action = self.timers_menu.addAction(self._timer_action_text(timer))
            timer_id = str(timer["timer_id"])
            self._timer_actions[timer_id] = action
            action.triggered.connect(
                lambda checked=False, value=timer_id: self._timer_manager.cancel_timer(value)
            )
            action.setToolTip(tr(self.lang, "cancel_timer"))
        self.timers_menu.addSeparator()
        cancel_all = self.timers_menu.addAction(tr(self.lang, "cancel_all_timers"))
        cancel_all.triggered.connect(self._timer_manager.cancel_all)

    def _timer_action_text(self, timer: dict) -> str:
        title = str(timer.get("message") or tr(self.lang, "quick_timer"))
        remaining = format_countdown(int(timer.get("remaining_ms", 0)))
        return f"{title} - {remaining}"

    def _show_timer_finished(self, timer: dict) -> None:
        message = str(timer.get("message") or tr(self.lang, "timer_finished"))
        self.showMessage(
            "FingerprintLauncher",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )
