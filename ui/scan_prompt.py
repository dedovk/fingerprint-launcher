"""Small bottom-right prompt shown while waiting for a fingerprint."""

from __future__ import annotations

from time import monotonic

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QApplication, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from ui.i18n import tr
from ui.theme import THEME


class ScanPrompt(QWidget):
    PROGRESS_DURATION_MS = 15000
    PROGRESS_MAX = 1000
    MIN_WIDTH = 380
    MAX_WIDTH = 550
    MIN_HEIGHT = 100
    MAX_HEIGHT = 400
    MESSAGE_VERTICAL_OVERHEAD = 76

    def __init__(self, lang: str = "uk", parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint,
        )
        self.lang = lang
        self.setObjectName("scanPrompt")
        self.setWindowTitle("FingerprintLauncher")
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.setMaximumSize(self.MAX_WIDTH, self.MAX_HEIGHT)
        self.resize(self.MIN_WIDTH, self.MIN_HEIGHT)
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
        self._progress_started_at: float | None = None
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(50)
        self._progress_timer.timeout.connect(self._advance_progress)
        self._progress_completing = False
        self._progress_completion_started_at = 0.0
        self._progress_completion_duration_ms = 0
        self._progress_completion_start_value = 0
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.hide)
        self.set_waiting(lang)

    def apply_theme(self) -> None:
        prompt_background = THEME.canvas_brush if THEME.is_gradient else THEME.surface
        self.setStyleSheet(
            f"""
            QWidget#scanPrompt {{
                background: {prompt_background};
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
            self._finish_progress_smoothly()
        else:
            self._progress_completing = False
        self.title.setText(tr(self.lang, "scan_popup_title"))
        self.message.setText(text)
        self._fit_message()
        if self.isVisible():
            self._move_to_bottom_right()

    def show_prompt(self, lang: str) -> None:
        self._close_timer.stop()
        self.progress.show()
        self.set_waiting(lang)
        self._start_progress()
        self._move_to_bottom_right()
        self.show()
        self.raise_()
        self.activateWindow()

    def close_later(self, ms: int = 1400) -> None:
        self._close_timer.start(ms)

    def show_notification(self, title: str, message: str, ms: int = 5000) -> None:
        self._progress_timer.stop()
        self._progress_completing = False
        self._close_timer.stop()
        self.progress.hide()
        self.title.setText(title)
        self.message.setText(message)
        self._fit_message()
        self._move_to_bottom_right()
        self.show()
        self.raise_()
        self.close_later(ms)

    def hide(self) -> None:  # type: ignore[override]
        self._progress_timer.stop()
        self._progress_completing = False
        self._close_timer.stop()
        super().hide()

    def _start_progress(self) -> None:
        self._progress_completing = False
        self._progress_started_at = monotonic()
        self.progress.setValue(0)
        self._progress_timer.start()

    def _advance_progress(self) -> None:
        if self._progress_completing:
            elapsed_ms = (monotonic() - self._progress_completion_started_at) * 1000
            fraction = min(1.0, elapsed_ms / self._progress_completion_duration_ms)
            eased = 1.0 - (1.0 - fraction) ** 3
            remaining = self.PROGRESS_MAX - self._progress_completion_start_value
            self.progress.setValue(
                self._progress_completion_start_value + int(remaining * eased)
            )
            if fraction >= 1.0:
                self.progress.setValue(self.PROGRESS_MAX)
                self._progress_completing = False
                self._progress_timer.stop()
            return
        if self._progress_started_at is None:
            return
        elapsed_ms = (monotonic() - self._progress_started_at) * 1000
        value = min(
            self.PROGRESS_MAX,
            int(self.PROGRESS_MAX * elapsed_ms / self.PROGRESS_DURATION_MS),
        )
        self.progress.setValue(value)
        if value >= self.PROGRESS_MAX:
            self._progress_timer.stop()

    def _finish_progress_smoothly(self) -> None:
        current = self.progress.value()
        if current >= self.PROGRESS_MAX:
            return
        remaining_ratio = (self.PROGRESS_MAX - current) / self.PROGRESS_MAX
        self._progress_completion_start_value = current
        self._progress_completion_duration_ms = max(
            90, min(260, int(260 * remaining_ratio))
        )
        self._progress_completion_started_at = monotonic()
        self._progress_completing = True
        self._progress_timer.start()

    def _fit_message(self) -> None:
        metrics = QFontMetrics(self.message.font())
        longest_line = max(self.message.text().splitlines() or [""], key=len)
        preferred_width = metrics.horizontalAdvance(longest_line) + 36
        target_width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, preferred_width))
        content_width = target_width - 36
        bounds = QFontMetrics(self.message.font()).boundingRect(
            QRect(0, 0, content_width, 1000),
            Qt.TextFlag.TextWordWrap,
            self.message.text(),
        )
        max_message_height = self.MAX_HEIGHT - self.MESSAGE_VERTICAL_OVERHEAD
        message_height = min(max_message_height, max(40, bounds.height() + 4))
        self.message.setFixedHeight(message_height)
        target_height = min(
            self.MAX_HEIGHT,
            max(self.MIN_HEIGHT, self.MESSAGE_VERTICAL_OVERHEAD + message_height),
        )
        self.resize(target_width, target_height)

    def _move_to_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        margin = 18
        self.move(rect.right() - self.width() - margin,
                  rect.bottom() - self.height() - margin)
