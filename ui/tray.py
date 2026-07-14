"""System tray integration."""

from __future__ import annotations

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from ui.i18n import tr
from ui.theme import THEME, configure_theme


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
        self.menu = QMenu()
        self.set_theme(THEME.key)
        self.menu.addAction(self.title_action)
        self.menu.addSeparator()
        self.menu.addAction(self.settings_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.setContextMenu(self.menu)

    def set_theme(self, theme_key: str) -> None:
        configure_theme(theme_key)
        self.menu.setStyleSheet(
            f"""
            QMenu {{
                background: {THEME.surface};
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
            """
        )

    def set_language(self, lang: str) -> None:
        self.lang = lang
        self.settings_action.setText(tr(lang, "settings_menu"))
        self.quit_action.setText(tr(lang, "quit"))
