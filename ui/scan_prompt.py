"""Small bottom-right prompt shown while waiting for a fingerprint."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from ui.i18n import tr


class ScanPrompt(QWidget):
    def __init__(self, lang: str = "uk") -> None:
        super().__init__(
            None,
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint,
        )
        self.lang = lang
        self.setWindowTitle("FingerprintLauncher")
        self.setMinimumSize(380, 100)
        self.setMaximumSize(550, 400)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(40)
        layout.addWidget(self.title)
        layout.addWidget(self.message)
        layout.addStretch()

        self.setStyleSheet(
            """
            QWidget {
                background: #111827;
                color: #f9fafb;
                border: 1px solid #374151;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
            """
        )
        self.set_waiting(lang)

    def set_waiting(self, lang: str) -> None:
        self.lang = lang
        self.title.setText(tr(lang, "scan_popup_title"))
        self.message.setText(tr(lang, "scan_popup_waiting"))

    def set_result(self, text: str) -> None:
        self.title.setText(tr(self.lang, "scan_popup_title"))
        self.message.setText(text)

    def show_prompt(self, lang: str) -> None:
        self.set_waiting(lang)
        self._move_to_bottom_right()
        self.show()
        self.raise_()
        self.activateWindow()

    def close_later(self, ms: int = 1400) -> None:
        QTimer.singleShot(ms, self.hide)

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        margin = 18
        self.move(rect.right() - self.width() - margin,
                  rect.bottom() - self.height() - margin)
