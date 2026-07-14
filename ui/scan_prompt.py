"""Small bottom-right prompt shown while waiting for a fingerprint."""

from __future__ import annotations

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QApplication, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from ui.i18n import tr
from ui.theme import THEME


class ScanPrompt(QWidget):
    PROGRESS_DURATION_MS = 15000
    PROGRESS_MAX = 1000

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
        self.resize(380, 100)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, self.PROGRESS_MAX)
        self.progress.setFixedHeight(4)
        layout.addWidget(self.progress)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight: 700; font-size: 14px; color: #1767DE;")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(40)
        self.message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.title)
        layout.addWidget(self.message)
        layout.addStretch()

        self.apply_theme()
        self._progress_elapsed = 0
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(50)
        self._progress_timer.timeout.connect(self._advance_progress)
        self.set_waiting(lang)

    def apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                background: {THEME.surface};
                color: {THEME.text};
                border: 1px solid {THEME.border};
                border-radius: 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
            QLabel {{
                color: {THEME.text};
            }}
            QProgressBar {{
                background: {THEME.disabled_bg};
                border: 0;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: #1767DE;
                border-radius: 2px;
            }}
            """
        )

    def set_waiting(self, lang: str) -> None:
        self.lang = lang
        self.title.setText(tr(lang, "scan_popup_title"))
        self.message.setText(tr(lang, "scan_popup_waiting"))
        self._fit_message()

    def set_result(self, text: str, complete: bool = False) -> None:
        self._progress_timer.stop()
        if complete:
            self.progress.setValue(self.PROGRESS_MAX)
        self.title.setText(tr(self.lang, "scan_popup_title"))
        self.message.setText(text)
        self._fit_message()
        if self.isVisible():
            self._move_to_bottom_right()

    def show_prompt(self, lang: str) -> None:
        self.set_waiting(lang)
        self._start_progress()
        self._move_to_bottom_right()
        self.show()
        self.raise_()
        self.activateWindow()

    def close_later(self, ms: int = 1400) -> None:
        QTimer.singleShot(ms, self.hide)

    def hide(self) -> None:  # type: ignore[override]
        self._progress_timer.stop()
        super().hide()

    def _start_progress(self) -> None:
        self._progress_elapsed = 0
        self.progress.setValue(0)
        self._progress_timer.start()

    def _advance_progress(self) -> None:
        self._progress_elapsed += self._progress_timer.interval()
        value = min(
            self.PROGRESS_MAX,
            int(self.PROGRESS_MAX * self._progress_elapsed / self.PROGRESS_DURATION_MS),
        )
        self.progress.setValue(value)
        if value >= self.PROGRESS_MAX:
            self._progress_timer.stop()

    def _fit_message(self) -> None:
        content_width = max(344, self.width() - 36)
        bounds = QFontMetrics(self.message.font()).boundingRect(
            QRect(0, 0, content_width, 1000),
            Qt.TextFlag.TextWordWrap,
            self.message.text(),
        )
        message_height = max(40, bounds.height() + 4)
        self.message.setFixedHeight(message_height)
        target_height = min(self.maximumHeight(), max(100, 76 + message_height))
        self.resize(max(380, self.width()), target_height)

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        margin = 18
        self.move(rect.right() - self.width() - margin,
                  rect.bottom() - self.height() - margin)
