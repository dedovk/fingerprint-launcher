"""System tray integration."""

from __future__ import annotations

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from ui.i18n import tr


class FingerprintTray(QSystemTrayIcon):
    def __init__(self, icon: QIcon, parent=None, lang: str = "uk") -> None:
        super().__init__(icon, parent)
        self.lang = lang
        self.title_action = QAction("FingerprintLauncher")
        self.title_action.setEnabled(False)
        self.settings_action = QAction()
        self.quit_action = QAction()
        self._build_menu()
        self.set_language(lang)

    def _build_menu(self) -> None:
        menu = QMenu()
        menu.addAction(self.title_action)
        menu.addSeparator()
        menu.addAction(self.settings_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        self.setContextMenu(menu)

    def set_language(self, lang: str) -> None:
        self.lang = lang
        self.settings_action.setText(tr(lang, "settings_menu"))
        self.quit_action.setText(tr(lang, "quit"))
