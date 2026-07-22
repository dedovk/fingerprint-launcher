"""Main settings window."""

from __future__ import annotations

from datetime import datetime
import ctypes
import ctypes.wintypes
import json
import re
import urllib.error
import urllib.request

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QObject, QRect, QRectF, QSize, Qt, QThread, QTimer, QUrl, QVariantAnimation, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont, QLinearGradient, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.action_registry import format_action_summary
from core.database import Database
from services.autostart import remove_user_autostart, setup_user_autostart
from services.timer_manager import TimerManager
from ui.finger_wizard import FingerWizard, HotkeyEdit
from ui.i18n import LANGUAGES, action_labels, tr
from ui.scan_prompt import ScanPrompt
from ui.theme import (
    THEME,
    StableComboBox,
    app_qss,
    configure_theme,
    icon,
    prepare_combo_popup,
    vertical_scrollbar_qss,
)
from ui.triggered_scan import TriggeredFingerprintScan
from core.time_utils import format_countdown, format_duration_ms


APP_VERSION = "1.0.0"
LATEST_RELEASE_API_URL = "https://api.github.com/repos/dedovk/fingerprint-launcher/releases/latest"
MONOBANK_JAR_URL = "https://send.monobank.ua/jar/389QJ6FiiC"
TRC20_WALLET_ADDRESS = "TD2JtNHKCu6o4pbu72frrUAM46K2Vc7E8q"
ACTIVITY_LOG_LIMIT = 10

STATUS_TEXTS = {
    "uk": {
        "warning": "Попередження",
        "activity_log": "Журнал активності",
        "activity_log_empty": "Журнал активності порожній",
        "scan_started": "Сканування відбитку пальця розпочато",
    },
    "en": {
        "warning": "Warning",
        "activity_log": "Activity log",
        "activity_log_empty": "Activity log is empty",
        "scan_started": "Fingerprint scan started",
    },
    "ru": {
        "warning": "Предупреждение",
        "activity_log": "Журнал активности",
        "activity_log_empty": "Журнал активности пуст",
        "scan_started": "Сканирование отпечатка пальца начато",
    },
    "fr": {
        "warning": "Avertissement",
        "activity_log": "Journal d'activité",
        "activity_log_empty": "Le journal d'activité est vide",
        "scan_started": "Scan de l'empreinte lancé",
    },
    "es": {
        "warning": "Advertencia",
        "activity_log": "Registro de actividad",
        "activity_log_empty": "El registro de actividad está vacío",
        "scan_started": "Escaneo de huella iniciado",
    },
}


def _status_text(lang: str, key: str) -> str:
    return STATUS_TEXTS.get(lang, STATUS_TEXTS["uk"]).get(key, STATUS_TEXTS["uk"][key])


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value.strip().lstrip("vV").split("-", 1)[0])
    return tuple(int(number) for number in numbers) or (0,)


def _is_newer_version(latest: str, current: str) -> bool:
    latest_parts = list(_version_tuple(latest))
    current_parts = list(_version_tuple(current))
    length = max(len(latest_parts), len(current_parts))
    latest_parts.extend([0] * (length - len(latest_parts)))
    current_parts.extend([0] * (length - len(current_parts)))
    return tuple(latest_parts) > tuple(current_parts)


class _UpdateCheckWorker(QObject):
    completed = pyqtSignal(dict)

    @pyqtSlot()
    def run(self) -> None:
        try:
            request = urllib.request.Request(
                LATEST_RELEASE_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"FingerprintLauncher/{APP_VERSION}",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    self.completed.emit({"ok": True, "no_releases": True})
                    return
                raise

            tag_name = str(payload.get("tag_name") or "").strip()
            if not tag_name:
                raise RuntimeError("GitHub release response did not include tag_name")

            self.completed.emit({
                "ok": True,
                "tag_name": tag_name,
                "html_url": str(payload.get("html_url") or ""),
            })
        except Exception as exc:
            self.completed.emit({"ok": False, "error": str(exc)})


class TitleBar(QFrame):
    def __init__(self, parent: QMainWindow, wizard: bool = False) -> None:
        super().__init__(parent)
        self.window = parent
        self.drag_pos = None
        self._drag_started_maximized = False
        self.setFixedHeight(45)
        self.setProperty("role", "titleWizard" if wizard else "titleMain")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

        if not wizard:
            app_icon = QLabel("FL")
            app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            app_icon.setFixedSize(16, 16)
            app_icon.setStyleSheet("background:#1D74F7;color:white;border-radius:2px;font-size:8px;font-weight:700;")
            layout.addWidget(app_icon)

        self.title = QLabel()
        self.title.setProperty("role", "wizardTitle" if wizard else "mainTitle")
        layout.addWidget(self.title)
        layout.addStretch()

        self.min_btn = QPushButton()
        self.min_btn.setProperty("iconName", "minimize_main_window")
        self.min_btn.setIconSize(QSize(12, 12))
        self.min_btn.setProperty("role", "wizardWindowButton" if wizard else "windowButton")
        minimize = getattr(parent, "animate_minimize", parent.showMinimized)
        self.min_btn.clicked.connect(minimize)
        layout.addWidget(self.min_btn)

        if not wizard:
            self.max_btn = QPushButton()
            self.max_btn.setProperty("iconName", "full_screen")
            self.max_btn.setIconSize(QSize(12, 12))
            self.max_btn.setProperty("role", "windowButton")
            self.max_btn.clicked.connect(self._toggle_maximized)
            layout.addWidget(self.max_btn)

        self.close_btn = QPushButton()
        self.close_btn.setProperty("iconName", "close_wizard" if wizard else "close_titlebar")
        self.close_btn.setIconSize(QSize(14, 14) if not wizard else QSize(10, 10))
        self.close_btn.setProperty("role", "wizardWindowButton" if wizard else "windowButton")
        self.close_btn.clicked.connect(parent.close)
        layout.addWidget(self.close_btn)
        self.refresh_icons()

    def refresh_icons(self) -> None:
        for button in self.findChildren(QPushButton):
            name = button.property("iconName")
            if name:
                button.setIcon(icon(str(name)))

    def _toggle_maximized(self) -> None:
        self.window.showNormal() if self.window.isMaximized() else self.window.showMaximized()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_started_maximized = self.window.isMaximized()
            self.drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self.window.isMaximized():
                normal_width = max(self.window.minimumWidth(), 780)
                self.window.showNormal()
                self.drag_pos.setX(normal_width // 2)
            self.window.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.drag_pos = None
        self._drag_started_maximized = False


class AnimatedTabButton(QPushButton):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setFixedHeight(34)
        self.setFixedWidth(133)
        self.setCheckable(True)
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(160)
        self.animation.valueChanged.connect(lambda value: self.setMaximumWidth(int(value)))

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(166 if active else 133)
        self.animation.start()
        if active:
            self.setStyleSheet(f"background:{THEME.tab_active};color:{THEME.tab_active_text};border:0;border-top-left-radius:10px;border-top-right-radius:10px;")
        else:
            self.setStyleSheet(f"background:{THEME.tab_inactive};color:{THEME.tab_inactive_text};border:0;border-top-left-radius:10px;border-top-right-radius:10px;")


class TabbedContent(QWidget):
    """Keep the page slightly above the tab bottoms, matching the reference."""

    OVERLAP = 6

    def __init__(self, tab_bar: QFrame, stack: QStackedWidget) -> None:
        super().__init__()
        self.tab_bar = tab_bar
        self.stack = stack
        self.tab_bar.setParent(self)
        self.stack.setParent(self)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        tab_height = 34
        stack_top = tab_height if THEME.is_gradient else tab_height - self.OVERLAP
        self.tab_bar.setGeometry(0, 0, self.width(), tab_height)
        self.stack.setGeometry(0, stack_top, self.width(), max(0, self.height() - stack_top))
        self.stack.raise_()


class ThemeSwatch(QWidget):
    clicked = pyqtSignal()

    def __init__(self, color: str | tuple[str, str], active: bool = False) -> None:
        super().__init__()
        self._gradient_colors = color if isinstance(color, tuple) else None
        self._color = QColor(color[0] if isinstance(color, tuple) else color)
        self._diameter = 38 if active else 34
        self._active = active
        self.setFixedSize(42, 42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent;")

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def set_diameter(self, diameter: int) -> None:
        self._diameter = diameter
        self.update()

    def diameter(self) -> int:
        return self._diameter

    def _outline_color(self) -> QColor | None:
        if self._active:
            return QColor(THEME.primary)
        if min(self._color.red(), self._color.green(), self._color.blue()) >= 240:
            return QColor("#111113")
        return None

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        diameter = self._diameter
        x = (self.width() - diameter) / 2
        y = (self.height() - diameter) / 2

        shadow_rect = QRectF(x + 1, y + 3, diameter - 2, diameter - 1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawEllipse(shadow_rect)

        if self._gradient_colors is not None:
            gradient = QLinearGradient(x, y, x + diameter, y + diameter)
            gradient.setColorAt(0.0, QColor(self._gradient_colors[0]))
            gradient.setColorAt(1.0, QColor(self._gradient_colors[1]))
            painter.setBrush(QBrush(gradient))
        else:
            painter.setBrush(self._color)
        outline = self._outline_color()
        painter.setPen(
            QPen(outline, 2 if self._active else 1)
            if outline is not None
            else Qt.PenStyle.NoPen
        )
        painter.drawEllipse(QRectF(x + 1, y + 1, diameter - 2, diameter - 2))

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ResizeHandle(QFrame):
    def __init__(self, window: "MainWindow", edges: set[str], cursor: Qt.CursorShape) -> None:
        super().__init__(window)
        self.window = window
        self.edges = edges
        self.setCursor(cursor)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent; border: 0;")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and not self.window.isMaximized():
            self.window._resize_edges = set(self.edges)
            self.window._resize_start_pos = event.globalPosition().toPoint()
            self.window._resize_start_geometry = self.window.geometry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.window._resize_edges and self.window._resize_start_pos is not None:
            self.window._resize_from_edges(event.globalPosition().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.window._resize_edges = set()
        self.window._resize_start_pos = None
        self.window._resize_start_geometry = QRect()
        super().mouseReleaseEvent(event)


class FingerTable(QTableWidget):
    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self.itemAt(event.position().toPoint()) is None:
            self.clearSelection()
            self.setCurrentItem(None)
            event.accept()
            return
        super().mousePressEvent(event)


def _button(text: str, kind: str, icon_name: str | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("kind", kind)
    if icon_name:
        btn.setProperty("iconName", icon_name)
        btn.setIcon(icon(icon_name))
        btn.setIconSize(QSize(14, 14))
    return btn


class SelectionRowDelegate(QStyledItemDelegate):
    @staticmethod
    def _paint_selected_chrome(painter, option, index, last_column: int) -> None:
        rect = option.rect
        painter.save()
        painter.setPen(QPen(QColor(THEME.border_focus), 1))
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.left(), rect.bottom() - 1, rect.right(), rect.bottom() - 1)
        if index.column() == 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(THEME.primary))
            painter.drawRect(rect.left(), rect.top() + 1, 3, max(1, rect.height() - 1))
            painter.setPen(QPen(QColor(THEME.border_focus), 1))
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        if index.column() == last_column:
            painter.setPen(QPen(QColor(THEME.border_focus), 1))
            painter.drawLine(rect.right() - 1, rect.top(), rect.right() - 1, rect.bottom())
        painter.restore()

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        if selected:
            painter.fillRect(opt.rect, QColor(THEME.selected_bg))
            opt.backgroundBrush = QBrush(QColor(THEME.selected_bg))
        else:
            if not THEME.is_gradient:
                painter.fillRect(opt.rect, QColor(THEME.bg))
        painter.restore()
        opt.state &= ~QStyle.StateFlag.State_Selected
        if selected and index.column() == 2:
            opt.palette.setColor(QPalette.ColorRole.Text, QColor(THEME.selected_action_text))
        super().paint(painter, opt, index)
        if selected:
            self._paint_selected_chrome(painter, option, index, 4)


class ActivityDelegate(SelectionRowDelegate):
    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        enabled = bool(index.data(Qt.ItemDataRole.UserRole + 1))
        color = QColor(THEME.success if enabled else THEME.danger)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        if selected:
            painter.fillRect(opt.rect, QColor(THEME.selected_bg))
        else:
            if not THEME.is_gradient:
                painter.fillRect(opt.rect, QColor(THEME.bg))
        icon_size = 14
        icon_rect = opt.rect.adjusted(20, 0, 0, 0)
        icon_rect.setWidth(icon_size)
        icon_rect.setHeight(icon_size)
        icon_rect.moveTop(opt.rect.top() + (opt.rect.height() - icon_size) // 2)
        opt.icon.paint(painter, icon_rect)
        text_rect = opt.rect.adjusted(40, 0, 4, 0)
        painter.setPen(color)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, opt.text)
        if selected:
            self._paint_selected_chrome(painter, option, index, 4)
        painter.restore()


def _card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("role", "card")
    frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(14)
    if title:
        label = QLabel(title)
        label.setProperty("role", "sectionTitle")
        layout.addWidget(label)
        line = QFrame()
        line.setFixedHeight(1)
        line.setProperty("role", "separator")
        layout.addWidget(line)
    return frame, layout


def _settings_card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setProperty("role", "settingsCard")
    frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return frame, layout


def _card_header(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "sectionTitle")
    label.setFixedHeight(54)
    label.setContentsMargins(20, 0, 20, 0)
    return label


def _separator() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setProperty("role", "separator")
    return line


class MainWindow(QMainWindow):
    language_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)
    activation_requested = pyqtSignal()

    def __init__(self, db: Database | None = None) -> None:
        super().__init__()
        self.db = db or Database()
        self.lang = self.db.get_setting("language", "uk") or "uk"
        self.theme_key = self.db.get_setting("theme", "light") or "light"
        if not configure_theme(self.theme_key):
            self.theme_key = "light"
            configure_theme(self.theme_key)
        self.scan_thread: QThread | None = None
        self.scan_worker: TriggeredFingerprintScan | None = None
        self.update_thread: QThread | None = None
        self.update_worker: _UpdateCheckWorker | None = None
        self._fade_animations: dict[QLabel, QPropertyAnimation] = {}
        self._update_status_key: str | None = None
        self._update_status_kwargs: dict[str, str] = {}
        self._swatch_animations: dict[QPushButton, QVariantAnimation] = {}
        self.hotkey_handle = None
        self.scan_prompt = ScanPrompt(self.lang, self)
        self.timer_notification = ScanPrompt(self.lang, self)
        self.allow_close = False
        self._minimize_animation: QParallelAnimationGroup | None = None
        self._minimize_restore_geometry = QRect()
        self._native_minimize_passthrough = False
        self._resize_margin = 8
        self._resize_edges: set[str] = set()
        self._resize_start_pos = None
        self._resize_start_geometry = QRect()
        self._activity_entries: list[tuple[str, str]] = []
        self._fingers_cache: dict[int, dict] = {}
        self._active_timers: list[dict] = []
        self.hotkey_paused = False
        self.timer_manager = TimerManager(self)
        self.timer_manager.timers_changed.connect(self._on_timers_changed)
        self.timer_manager.timer_started.connect(self._on_timer_started)
        self.timer_manager.timer_finished.connect(self._on_timer_finished)
        self.timer_manager.timer_cancelled.connect(self._on_timer_cancelled)
        self.activation_requested.connect(self.start_triggered_scan)

        self.setWindowTitle("FingerprintLauncher")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.resize(780, 830)
        self.setMinimumSize(780, 830)
        self.setStyleSheet(app_qss())

        root = QWidget()
        root.setProperty("role", "canvas")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.title_bar = TitleBar(self)
        root_layout.addWidget(self.title_bar)

        self.tab_bar = QFrame()
        self.tab_bar.setProperty("role", "tabBar")
        tab_layout = QHBoxLayout(self.tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        self.tab_buttons = [AnimatedTabButton(""), AnimatedTabButton(""), AnimatedTabButton("")]
        for index, tab in enumerate(self.tab_buttons):
            tab.clicked.connect(lambda checked=False, i=index: self.set_tab(i))
            tab_layout.addWidget(tab)
        tab_layout.addStretch()
        self.stack = QStackedWidget()
        self.stack.setProperty("role", "canvasStack")
        self.stack.addWidget(self._fingers_tab())
        self.stack.addWidget(self._status_tab())
        self.stack.addWidget(self._settings_tab())
        self.tabbed_content = TabbedContent(self.tab_bar, self.stack)
        self.tabbed_content.setProperty("role", "canvasContainer")
        root_layout.addWidget(self.tabbed_content, 1)
        self.setCentralWidget(root)
        self._resize_handles = self._create_resize_handles()
        self._position_resize_handles()

        self.retranslate()
        self.set_tab(0)
        self.refresh_fingers()
        self._apply_theme_visuals()
        self.register_activation_hotkey()

    def set_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, tab in enumerate(self.tab_buttons):
            tab.set_active(i == index)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if hasattr(self, "_resize_handles"):
            self._position_resize_handles()

    def _create_resize_handles(self) -> list[ResizeHandle]:
        return [
            ResizeHandle(self, {"left"}, Qt.CursorShape.SizeHorCursor),
            ResizeHandle(self, {"right"}, Qt.CursorShape.SizeHorCursor),
            ResizeHandle(self, {"top"}, Qt.CursorShape.SizeVerCursor),
            ResizeHandle(self, {"bottom"}, Qt.CursorShape.SizeVerCursor),
            ResizeHandle(self, {"left", "top"}, Qt.CursorShape.SizeFDiagCursor),
            ResizeHandle(self, {"right", "top"}, Qt.CursorShape.SizeBDiagCursor),
            ResizeHandle(self, {"left", "bottom"}, Qt.CursorShape.SizeBDiagCursor),
            ResizeHandle(self, {"right", "bottom"}, Qt.CursorShape.SizeFDiagCursor),
        ]

    def _position_resize_handles(self) -> None:
        margin = self._resize_margin
        width = self.width()
        height = self.height()
        specs = [
            (0, margin, margin, max(0, height - margin * 2)),
            (width - margin, margin, margin, max(0, height - margin * 2)),
            (margin, 0, max(0, width - margin * 2), margin),
            (margin, height - margin, max(0, width - margin * 2), margin),
            (0, 0, margin, margin),
            (width - margin, 0, margin, margin),
            (0, height - margin, margin, margin),
            (width - margin, height - margin, margin, margin),
        ]
        enabled = not self.isMaximized()
        for handle, geometry in zip(self._resize_handles, specs):
            handle.setGeometry(*geometry)
            handle.setVisible(enabled)
            handle.raise_()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._hit_resize_edges(event.position().toPoint())
            if edges:
                self._resize_edges = edges
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._resize_edges and self._resize_start_pos is not None:
            self._resize_from_edges(event.globalPosition().toPoint())
            event.accept()
            return
        self._update_resize_cursor(event.position().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._resize_edges = set()
        self._resize_start_pos = None
        self._resize_start_geometry = QRect()
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def _hit_resize_edges(self, pos) -> set[str]:
        margin = self._resize_margin
        edges: set[str] = set()
        if pos.x() <= margin:
            edges.add("left")
        elif pos.x() >= self.width() - margin:
            edges.add("right")
        if pos.y() <= margin:
            edges.add("top")
        elif pos.y() >= self.height() - margin:
            edges.add("bottom")
        return edges

    def _update_resize_cursor(self, pos) -> None:
        edges = self._hit_resize_edges(pos)
        if {"left", "top"} <= edges or {"right", "bottom"} <= edges:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif {"right", "top"} <= edges or {"left", "bottom"} <= edges:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edges & {"left", "right"}:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges & {"top", "bottom"}:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def _resize_from_edges(self, global_pos) -> None:
        delta = global_pos - self._resize_start_pos
        geometry = QRect(self._resize_start_geometry)
        min_width = self.minimumWidth()
        min_height = self.minimumHeight()
        if "left" in self._resize_edges:
            new_left = min(geometry.right() - min_width + 1, geometry.left() + delta.x())
            geometry.setLeft(new_left)
        if "right" in self._resize_edges:
            geometry.setRight(max(geometry.left() + min_width - 1, geometry.right() + delta.x()))
        if "top" in self._resize_edges:
            new_top = min(geometry.bottom() - min_height + 1, geometry.top() + delta.y())
            geometry.setTop(new_top)
        if "bottom" in self._resize_edges:
            geometry.setBottom(max(geometry.top() + min_height - 1, geometry.bottom() + delta.y()))
        self.setGeometry(geometry)

    def _fingers_tab(self) -> QWidget:
        page = QWidget()
        page.setProperty("role", "canvasPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.fingers_table = FingerTable(0, 5)
        self.fingers_table.verticalHeader().setVisible(False)
        self.fingers_table.setShowGrid(False)
        self.fingers_table.setWordWrap(False)
        self.fingers_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.fingers_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.fingers_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.fingers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.fingers_table.setSortingEnabled(False)
        self.fingers_table.verticalScrollBar().setStyleSheet(vertical_scrollbar_qss())
        self.fingers_table.horizontalHeader().setFixedHeight(37)
        self.fingers_table.horizontalHeader().setSectionsMovable(False)
        self.fingers_table.horizontalHeader().setCascadingSectionResizes(False)
        self.fingers_table.horizontalHeader().setMinimumSectionSize(44)
        self.fingers_table.setColumnWidth(0, 48)
        self.fingers_table.setColumnWidth(1, 160)
        self.fingers_table.setColumnWidth(2, 180)
        self.fingers_table.setColumnWidth(4, 126)
        self.fingers_table.horizontalHeader().setStretchLastSection(False)
        self.fingers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.fingers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.fingers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.fingers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.fingers_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.fingers_table.setItemDelegate(SelectionRowDelegate(self.fingers_table))
        self.fingers_table.setItemDelegateForColumn(4, ActivityDelegate(self.fingers_table))
        self.fingers_table.cellClicked.connect(self._on_fingers_cell_clicked)
        layout.addWidget(self.fingers_table, 1)

        footer = QFrame()
        footer.setProperty("role", "footer")
        footer.setFixedHeight(71)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 16, 20, 16)
        footer_layout.setSpacing(8)
        self.add_btn = _button("", "primary", "add")
        self.edit_btn = _button("", "secondary", "edit")
        self.delete_btn = _button("", "secondary", "delete")
        self.add_btn.setFixedSize(104, 36)
        self.edit_btn.setFixedSize(146, 38)
        self.delete_btn.setFixedSize(120, 38)
        self.add_btn.clicked.connect(self.add_finger)
        self.edit_btn.clicked.connect(self.edit_selected_finger)
        self.delete_btn.clicked.connect(self.delete_selected_finger)
        footer_layout.addWidget(self.add_btn)
        footer_layout.addWidget(self.edit_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(self.delete_btn)
        layout.addWidget(footer)
        return page

    def _status_tab(self) -> QWidget:
        page = QWidget()
        page.setProperty("role", "canvasPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 0, 20, 20)
        layout.setSpacing(16)
        self.status_card, status_layout = _card()
        self.status_title = QLabel()
        self.status_title.setProperty("role", "fieldLabel")
        self.monitor_status = QLabel()
        self.monitor_status.setStyleSheet(f"color:{THEME.subtle};")
        self.hotkey_chip = QLabel()
        self.hotkey_chip.setProperty("role", "mono")
        self.hotkey_chip.setStyleSheet(self._hotkey_chip_style())
        self.status_title.setStyleSheet(f"color:{THEME.subtle};")
        row = QHBoxLayout()
        row.setContentsMargins(20, 4, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.monitor_status)
        row.addWidget(self.hotkey_chip)
        row.addStretch()
        status_layout.addWidget(self.status_title)
        status_layout.addLayout(row)
        layout.addWidget(self.status_card)

        self.warning_card, warning_layout = _card()
        warning_row = QHBoxLayout()
        warning_row.setSpacing(16)
        self.status_detail_icon = QLabel()
        self.status_detail_icon.setPixmap(icon("alert").pixmap(18, 18))
        self.status_detail_icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.warning_text = QLabel()
        self.warning_text.setWordWrap(True)
        self.warning_text.setStyleSheet(f"color:{THEME.subtle};line-height:1.45;")
        warning_row.addWidget(self.status_detail_icon)
        warning_row.addWidget(self.warning_text, 1)
        warning_layout.addLayout(warning_row)
        self.warning_card.setStyleSheet(self._status_card_style(THEME.warning_bg))
        self.warning_card.hide()
        layout.addWidget(self.warning_card)

        self.activity_log_card, activity_layout = _settings_card()
        self.activity_log_card.setProperty("role", "statusLog")
        activity_header = QWidget()
        activity_header.setStyleSheet("background:transparent;")
        activity_header.setFixedHeight(36)
        activity_header_layout = QHBoxLayout(activity_header)
        activity_header_layout.setContentsMargins(20, 0, 20, 0)
        self.activity_log_title = QLabel()
        self.activity_log_title.setProperty("role", "fieldLabel")
        activity_header_layout.addWidget(self.activity_log_title)
        activity_layout.addWidget(activity_header)
        activity_layout.addWidget(_separator())
        self.activity_log_rows = QWidget()
        self.activity_log_rows.setStyleSheet("background:transparent;")
        self.activity_log_rows_layout = QVBoxLayout(self.activity_log_rows)
        self.activity_log_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.activity_log_rows_layout.setSpacing(0)
        activity_layout.addWidget(self.activity_log_rows)
        self.activity_log_card.setMinimumHeight(406)
        layout.addWidget(self.activity_log_card, 1)
        self.last_activity = QLabel()
        self._last_status_mode = ""
        self._last_status_message = ""
        return page

    def _settings_tab(self) -> QWidget:
        page = QWidget()
        page.setProperty("role", "canvasPage")
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(20, 0, 20, 20)
        outer_layout.setSpacing(23)
        content = QWidget()
        content.setProperty("role", "canvasContainer")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(23)
        outer_layout.addWidget(content, 0, Qt.AlignmentFlag.AlignTop)
        outer_layout.addStretch()

        self.app_card, app_layout = _settings_card()
        self.app_card.setFixedHeight(136)
        app_header = QWidget()
        app_header.setStyleSheet("background:transparent;")
        app_header.setFixedHeight(44)
        app_header_layout = QHBoxLayout(app_header)
        app_header_layout.setContentsMargins(20, 0, 20, 0)
        app_header_layout.setSpacing(12)
        self.app_title = QLabel()
        self.app_title.setProperty("role", "sectionTitle")
        app_header_layout.addWidget(self.app_title)
        app_header_layout.addStretch()
        app_layout.addWidget(app_header)
        app_layout.addWidget(_separator())
        app_body = QHBoxLayout()
        app_body.setContentsMargins(20, 8, 20, 8)
        app_body.setSpacing(28)
        self.autostart = QCheckBox()
        self.autostart.setChecked(self.db.get_setting("autostart", "0") == "1")
        self.autostart.stateChanged.connect(self.toggle_autostart)
        app_body.addWidget(self.autostart, 1, Qt.AlignmentFlag.AlignVCenter)
        autostart_mode_box = QVBoxLayout()
        autostart_mode_box.setContentsMargins(0, 0, 0, 0)
        autostart_mode_box.setSpacing(6)
        self.autostart_mode_label = QLabel()
        self.autostart_mode_label.setProperty("role", "muted")
        self.autostart_mode_label.setStyleSheet(f"font-size:14px;color:{THEME.muted};")
        self.autostart_mode_combo = StableComboBox()
        self.autostart_mode_combo.setProperty("role", "settingsInput")
        self.autostart_mode_combo.setFixedSize(288, 42)
        prepare_combo_popup(self.autostart_mode_combo)
        self.autostart_mode_combo.view().setMinimumWidth(340)
        self.autostart_mode_combo.currentIndexChanged.connect(self.change_autostart_mode)
        autostart_mode_box.addWidget(self.autostart_mode_label)
        autostart_mode_box.addWidget(self.autostart_mode_combo)
        app_body.addLayout(autostart_mode_box)
        app_layout.addLayout(app_body)
        layout.addWidget(self.app_card)

        self.activation_card, activation_layout = _settings_card()
        self.activation_card.setFixedHeight(154)
        self.activation_title = _card_header()
        self.activation_title.setFixedHeight(44)
        self.activation_hotkey_label = QLabel()
        self.activation_hotkey_label.setProperty("role", "fieldLabel")
        self.activation_hotkey_input = HotkeyEdit(capture_only=True)
        self.activation_hotkey_input.setProperty("role", "mono")
        self.activation_hotkey_input.setFixedHeight(42)
        self.activation_hotkey_input.setText(self.activation_hotkey())
        self.activation_hotkey_save = _button("", "primary")
        self.activation_hotkey_save.setFixedSize(97, 36)
        self.activation_hotkey_save.clicked.connect(self.save_activation_hotkey)
        activation_layout.addWidget(self.activation_title)
        activation_layout.addWidget(_separator())
        form_row = QHBoxLayout()
        form_row.setContentsMargins(20, 8, 20, 12)
        form_row.setSpacing(8)
        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(self.activation_hotkey_label)
        left.addWidget(self.activation_hotkey_input)
        form_row.addLayout(left, 1)
        form_row.addWidget(self.activation_hotkey_save, 0, Qt.AlignmentFlag.AlignBottom)
        activation_layout.addLayout(form_row)
        layout.addWidget(self.activation_card)

        self.appearance_card, appearance_layout = _settings_card()
        self.appearance_card.setFixedHeight(214)
        self.appearance_title = _card_header()
        self.appearance_title.setFixedHeight(44)
        appearance_layout.addWidget(self.appearance_title)
        appearance_layout.addWidget(_separator())
        appearance_body = QVBoxLayout()
        appearance_body.setContentsMargins(20, 10, 20, 14)
        appearance_body.setSpacing(10)
        appearance_grid = QGridLayout()
        appearance_grid.setHorizontalSpacing(34)
        appearance_grid.setVerticalSpacing(8)
        appearance_grid.setColumnStretch(0, 1)
        appearance_grid.setColumnStretch(1, 1)
        self.theme_label = QLabel()
        self.theme_label.setProperty("role", "fieldLabel")
        self.language_label = QLabel()
        self.language_label.setProperty("role", "fieldLabel")
        appearance_grid.addWidget(self.theme_label, 0, 0)
        appearance_grid.addWidget(self.language_label, 0, 1)
        self.swatch_row = QHBoxLayout()
        self.swatch_row.setSpacing(10)
        self._theme_buttons: list[ThemeSwatch] = []
        current_theme = self.theme_key
        for key, color, name_key in [
            ("light", "#F9FAFB", "theme_light"),
            ("onyx", "#000100", "theme_onyx"),
            ("graphite", "#323338", "theme_graphite"),
            ("dark", "#121A2F", "theme_dark"),
            ("purple_gradient", "#2A123E", "theme_purple"),
            ("blue_gradient", ("#0B1120", "#1E3A8A"), "theme_blue"),
        ]:
            swatch = ThemeSwatch(color, key == current_theme)
            swatch.setToolTip(tr(self.lang, name_key))
            swatch.setProperty("theme_key", key)
            swatch.setProperty("theme_name_key", name_key)
            swatch.clicked.connect(lambda k=key: self.change_theme_key(k))
            self._theme_buttons.append(swatch)
            self.swatch_row.addWidget(swatch)
        self.swatch_row.addStretch()
        self.language_combo = StableComboBox()
        self.language_combo.setProperty("role", "settingsInput")
        self.language_combo.setFixedHeight(42)
        prepare_combo_popup(self.language_combo)
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.lang)))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        appearance_grid.addLayout(self.swatch_row, 1, 0)
        appearance_grid.addWidget(self.language_combo, 1, 1)
        appearance_body.addLayout(appearance_grid)
        appearance_body.addWidget(_separator())
        version_row = QHBoxLayout()
        version_row.setContentsMargins(0, 0, 0, 0)
        version_row.setSpacing(6)
        self.version_label = QLabel()
        self.version_value = QLabel(APP_VERSION)
        self.version_value.setProperty("role", "mono")
        self.check_updates_btn = _button("", "secondary", "check_version")
        self.check_updates_btn.setMinimumWidth(176)
        self.check_updates_btn.clicked.connect(self.check_for_updates)
        self.language_combo.set_covered_widgets([self.check_updates_btn])
        self.update_status = QLabel()
        self.update_status.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.update_status.setWordWrap(True)
        self.update_status.setFixedHeight(22)
        self.update_status.setMinimumWidth(230)
        version_row.addWidget(self.version_label)
        version_row.addWidget(self.version_value)
        version_row.addSpacing(14)
        version_row.addWidget(self.update_status, 1)
        version_row.addStretch()
        version_row.addWidget(self.check_updates_btn)
        appearance_body.addLayout(version_row)
        appearance_layout.addLayout(appearance_body)
        self.update_status.setText(" ")
        layout.addWidget(self.appearance_card)

        self.support_card, support_layout = _settings_card()
        self.support_card.setFixedHeight(156)
        support_head = QHBoxLayout()
        support_head.setContentsMargins(20, 0, 20, 0)
        support_head.setSpacing(10)
        self.support_icon = QLabel()
        self.support_icon.setFixedSize(28, 28)
        self.support_icon.setPixmap(icon("support").pixmap(28, 28))
        self.support_title = QLabel()
        self.support_title.setProperty("role", "sectionTitle")
        support_head.addWidget(self.support_icon)
        support_head.addWidget(self.support_title)
        support_head.addStretch()
        support_header = QWidget()
        support_header.setFixedHeight(44)
        support_header.setStyleSheet("background: transparent;")
        support_header.setLayout(support_head)
        support_layout.addWidget(support_header)
        support_layout.addWidget(_separator())
        support_body = QVBoxLayout()
        support_body.setContentsMargins(20, 10, 20, 12)
        support_body.setSpacing(8)
        self.support_text = QLabel()
        self.support_text.setProperty("role", "muted")
        support_body.addWidget(self.support_text)
        support_actions = QHBoxLayout()
        support_actions.setSpacing(8)
        self.monobank_btn = QPushButton()
        self.monobank_btn.setFixedSize(40, 40)
        self.monobank_btn.setIcon(icon("mono_button"))
        self.monobank_btn.setIconSize(QSize(40, 40))
        self.monobank_btn.setStyleSheet("border:0;background:transparent;padding:0;min-width:40px;max-width:40px;min-height:40px;max-height:40px;")
        self.monobank_btn.clicked.connect(self.open_monobank_support)
        self.trc20_label = QLabel("TRC20 address")
        self.trc20_label.setStyleSheet(self._trc20_style())
        self.copy_trc20_btn = _button("", "primary", "copy")
        self.copy_trc20_btn.setFixedSize(122, 28)
        self.copy_trc20_btn.clicked.connect(self.copy_trc20_address)
        self.copy_status = QLabel()
        support_actions.addWidget(self.monobank_btn)
        support_actions.addWidget(self.trc20_label)
        support_actions.addWidget(self.copy_trc20_btn)
        support_actions.addWidget(self.copy_status)
        support_actions.addStretch()
        support_body.addLayout(support_actions)
        support_layout.addLayout(support_body)
        layout.addWidget(self.support_card)
        layout.addStretch()
        return page

    def _swatch_style(self, color: str, active: bool) -> str:
        return ""

    def _hotkey_chip_style(self) -> str:
        background = "transparent" if THEME.key != "light" else THEME.secondary
        return (
            f"background:{background};color:{THEME.subtle};border-radius:8px;"
            "padding:2px 10px;font-size:12px;font-weight:700;"
        )

    def _status_card_style(self, background: str) -> str:
        return (
            "QFrame[role='card']{"
            f"background:{background};border:0;border-radius:14px;"
            "}"
        )

    def _trc20_style(self) -> str:
        return (
            f"background:{THEME.trc_bg};color:{THEME.trc_text};border:1px solid {THEME.trc_border};"
            "border-radius:10px;padding:6px 14px;"
        )

    def retranslate(self) -> None:
        self.title_bar.title.setText("FingerprintLauncher")
        for button, key in zip(self.tab_buttons, ("my_fingers", "status", "settings"), strict=True):
            button.setText(tr(self.lang, key))
        self.fingers_table.setHorizontalHeaderLabels(["#", tr(self.lang, "finger").upper(), tr(self.lang, "action").upper(), tr(self.lang, "command").upper(), tr(self.lang, "activity").upper()])
        self.add_btn.setText(tr(self.lang, "add"))
        self.edit_btn.setText(tr(self.lang, "edit"))
        self.delete_btn.setText(tr(self.lang, "delete"))
        self._fit_translated_button(self.add_btn, 104)
        self._fit_translated_button(self.edit_btn, 146)
        self._fit_translated_button(self.delete_btn, 120)
        self.status_title.setText(tr(self.lang, "status").upper())
        self.activity_log_title.setText(_status_text(self.lang, "activity_log").upper())
        self.app_title.setText(tr(self.lang, "startup"))
        self.activation_title.setText(tr(self.lang, "activation"))
        self.appearance_title.setText(tr(self.lang, "appearance"))
        self.support_title.setText(tr(self.lang, "support_project"))
        self.autostart.setText(tr(self.lang, "autostart"))
        self.autostart_mode_label.setText(tr(self.lang, "autostart_mode"))
        current_mode = self._current_autostart_mode()
        self.autostart_mode_combo.blockSignals(True)
        self.autostart_mode_combo.clear()
        self.autostart_mode_combo.addItem(tr(self.lang, "autostart_disabled"), "disabled")
        self.autostart_mode_combo.addItem(tr(self.lang, "autostart_current_user"), "current_user")
        self.autostart_mode_combo.addItem(tr(self.lang, "autostart_current_user_tray"), "current_user_tray")
        self.autostart_mode_combo.setCurrentIndex(max(0, self.autostart_mode_combo.findData(current_mode)))
        self.autostart_mode_combo.blockSignals(False)
        self.activation_hotkey_label.setText(tr(self.lang, "activation_hotkey").upper())
        self.activation_hotkey_save.setText(tr(self.lang, "save"))
        self._fit_translated_button(self.activation_hotkey_save, 97)
        self.theme_label.setText(tr(self.lang, "theme").upper())
        self.language_label.setText(tr(self.lang, "language").upper())
        self.version_label.setText(tr(self.lang, "version"))
        self.check_updates_btn.setText(tr(self.lang, "check_updates"))
        self._fit_translated_button(self.check_updates_btn, 176)
        self.support_text.setText(tr(self.lang, "support_text"))
        self.copy_trc20_btn.setText(tr(self.lang, "copy"))
        self._fit_translated_button(self.copy_trc20_btn, 122)
        for button in self._theme_buttons:
            button.setToolTip(tr(self.lang, str(button.property("theme_name_key"))))
        self._set_status_detail(self._last_status_mode, self._last_status_message)
        self._render_activity_log()
        if self.update_status.text().strip() and self._update_status_key:
            self.update_status.setText(
                tr(self.lang, self._update_status_key).format(**self._update_status_kwargs)
            )
        elif not self.update_status.text() or self.update_status.text() == " ":
            self.update_status.setText(" ")
        if self.copy_status.text().strip():
            self.copy_status.setText(tr(self.lang, "copied"))
        self.refresh_status()
        self.refresh_fingers()

    def refresh_fingers(self) -> None:
        self.fingers_table.setRowCount(0)
        labels = action_labels(self.lang)
        fingers_dict = {}
        for item in self.db.list_fingers():
            finger_id = item["id"]
            fingers_dict.setdefault(finger_id, {"id": finger_id, "label": item["label"], "commands": []})
            if item.get("command_type"):
                fingers_dict[finger_id]["commands"].append({
                    "command_id": item.get("command_id"),
                    "command_type": item.get("command_type"),
                    "command_data": item.get("command_data"),
                    "enabled": bool(item.get("enabled", 1)),
                })

        self._fingers_cache = fingers_dict

        for index, finger in enumerate(fingers_dict.values(), start=1):
            row = self.fingers_table.rowCount()
            self.fingers_table.insertRow(row)
            self.fingers_table.setRowHeight(row, 57)
            num_item = QTableWidgetItem(str(index))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.fingers_table.setItem(row, 0, num_item)
            finger_item = QTableWidgetItem(str(finger["label"]))
            finger_item.setData(Qt.ItemDataRole.UserRole, finger["id"])
            finger_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.fingers_table.setItem(row, 1, finger_item)
            action_types = ", ".join(labels.get(cmd["command_type"], cmd["command_type"]) for cmd in finger["commands"]) if finger["commands"] else tr(self.lang, "no_action")
            action_item = QTableWidgetItem(action_types)
            action_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.fingers_table.setItem(row, 2, action_item)
            summaries = []
            for cmd in finger["commands"]:
                summary = format_action_summary(
                    cmd["command_type"],
                    cmd.get("command_data"),
                    labels.get(cmd["command_type"], cmd["command_type"]),
                )
                if summary:
                    summaries.append(summary)
            command_item = QTableWidgetItem(" | ".join(summaries))
            command_item.setFont(QFont(THEME.mono_font, 10))
            command_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.fingers_table.setItem(row, 3, command_item)
            commands = finger["commands"]
            sequence_enabled = bool(commands) and all(
                command.get("enabled", False) for command in commands
            )
            self.fingers_table.setItem(
                row,
                4,
                self._status_item(sequence_enabled, int(finger["id"])),
            )

        self._render_timer_countdowns()

    def _on_timers_changed(self, timers: list[dict]) -> None:
        self._active_timers = list(timers)
        self._render_timer_countdowns()

    def _render_timer_countdowns(self) -> None:
        if not hasattr(self, "fingers_table"):
            return
        labels = action_labels(self.lang)
        timers_by_command: dict[int, list[dict]] = {}
        for timer in self._active_timers:
            command_id = timer.get("command_id")
            if command_id is not None:
                timers_by_command.setdefault(int(command_id), []).append(timer)

        for row in range(self.fingers_table.rowCount()):
            finger_item = self.fingers_table.item(row, 1)
            if finger_item is None:
                continue
            finger_id = int(finger_item.data(Qt.ItemDataRole.UserRole))
            finger = self._fingers_cache.get(finger_id, {})
            summaries: list[str] = []
            for command in finger.get("commands", []):
                command_timers = sorted(
                    timers_by_command.get(int(command.get("command_id") or -1), []),
                    key=lambda item: item.get("remaining_ms", 0),
                )
                if command["command_type"] == "quick_timer" and command_timers:
                    remaining = format_countdown(command_timers[0]["remaining_ms"])
                    summary = tr(self.lang, "timer_remaining").format(remaining=remaining)
                    if len(command_timers) > 1:
                        summary += " · " + tr(self.lang, "timer_more").format(
                            count=len(command_timers) - 1
                        )
                else:
                    summary = format_action_summary(
                        command["command_type"],
                        command.get("command_data"),
                        labels.get(command["command_type"], command["command_type"]),
                    )
                if summary:
                    summaries.append(summary)
            item = self.fingers_table.item(row, 3)
            if item is not None:
                item.setText(" | ".join(summaries))

    def _timer_display_name(self, timer: dict) -> str:
        return str(timer.get("message") or tr(self.lang, "quick_timer"))

    def _on_timer_started(self, timer: dict) -> None:
        message = tr(self.lang, "timer_started").format(
            duration=format_duration_ms(int(timer["duration_ms"]))
        )
        title = self._timer_display_name(timer)
        self._append_activity(f"{message} · {title}")

    def _on_timer_finished(self, timer: dict) -> None:
        message = f"{tr(self.lang, 'timer_finished')}: {self._timer_display_name(timer)}"
        self.last_activity.setText(message)
        self._append_activity(message)
        self._set_status_detail("success", message)
        self.timer_notification.show_notification(
            tr(self.lang, "timer_finished"),
            self._timer_display_name(timer),
        )

    def _on_timer_cancelled(self, timer: dict) -> None:
        self._append_activity(
            f"{tr(self.lang, 'timer_cancelled')}: {self._timer_display_name(timer)}"
        )

    def _set_status_detail(self, mode: str, message: str) -> None:
        self._last_status_mode = mode
        self._last_status_message = message
        if not mode or not message:
            self.warning_card.hide()
            return
        self.warning_card.show()
        if mode == "success":
            self.status_detail_icon.setPixmap(icon("active_action").pixmap(18, 18))
            self.warning_card.setStyleSheet(self._status_card_style(THEME.success_bg))
            self.warning_text.setText(f"<b>{tr(self.lang, 'executed')}</b><br>{message}")
            return

        self.status_detail_icon.setPixmap(icon("alert").pixmap(18, 18))
        self.warning_card.setStyleSheet(self._status_card_style(THEME.warning_bg))
        unknown_hello = tr(self.lang, "unknown_hello").replace("\n", " ")
        if message == unknown_hello or "Windows Hello" in message:
            self.warning_text.setText(
                f"<b>{tr(self.lang, 'warning_hello_title')}</b><br>"
                f"{tr(self.lang, 'warning_hello_body')}"
            )
        else:
            self.warning_text.setText(f"<b>{_status_text(self.lang, 'warning')}</b><br>{message}")

    def _append_activity(self, message: str) -> None:
        self._activity_entries.insert(0, (datetime.now().strftime("%H:%M:%S"), message))
        self._activity_entries = self._activity_entries[:ACTIVITY_LOG_LIMIT]
        self._render_activity_log()

    def _render_activity_log(self) -> None:
        while self.activity_log_rows_layout.count():
            item = self.activity_log_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        entries = self._activity_entries or [("--:--:--", _status_text(self.lang, "activity_log_empty"))]
        for index, (time_text, message) in enumerate(entries):
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            row.setFixedHeight(36)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(20, 0, 20, 0)
            row_layout.setSpacing(12)
            time_label = QLabel(time_text)
            time_label.setFixedWidth(58)
            time_label.setStyleSheet(f"color:{THEME.subtle};font-family:{THEME.mono_font},monospace;font-size:12px;")
            divider = QLabel("|")
            divider.setStyleSheet(f"color:{THEME.border};")
            message_label = QLabel(message)
            message_label.setStyleSheet(f"color:{THEME.subtle};")
            message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row_layout.addWidget(time_label)
            row_layout.addWidget(divider)
            row_layout.addWidget(message_label, 1)
            self.activity_log_rows_layout.addWidget(row)
            if index < len(entries) - 1:
                self.activity_log_rows_layout.addWidget(_separator())

    def _status_item(self, enabled: bool, finger_id: int) -> QTableWidgetItem:
        item = QTableWidgetItem(tr(self.lang, "enabled") if enabled else tr(self.lang, "disabled"))
        item.setIcon(icon("active_action" if enabled else "inactive_action"))
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        item.setForeground(QBrush(QColor(THEME.success if enabled else THEME.danger)))
        item.setData(Qt.ItemDataRole.UserRole, finger_id)
        item.setData(Qt.ItemDataRole.UserRole + 1, enabled)
        return item

    def _on_fingers_cell_clicked(self, row: int, column: int) -> None:
        if column != 4:
            return
        item = self.fingers_table.item(row, column)
        if item is None:
            return
        finger_id = item.data(Qt.ItemDataRole.UserRole)
        if finger_id is None:
            return
        enabled = not bool(item.data(Qt.ItemDataRole.UserRole + 1))
        self.db.set_finger_commands_enabled(int(finger_id), enabled)
        self.refresh_fingers()

    @staticmethod
    def _fit_translated_button(button: QPushButton, minimum_width: int) -> None:
        button.setFixedWidth(max(minimum_width, button.sizeHint().width()))

    def refresh_status(self) -> None:
        if self.hotkey_paused:
            self.monitor_status.setText(tr(self.lang, "hotkey_paused"))
            self.hotkey_chip.setText("")
            return
        self.monitor_status.setText(tr(self.lang, "hotkey_status").split("{hotkey}")[0].format(hotkey="").rstrip(": ") + ":")
        self.hotkey_chip.setText(self.activation_hotkey())

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
        item = self.fingers_table.item(selected[0].row(), 1)
        return self._finger_by_id(int(item.data(Qt.ItemDataRole.UserRole))) if item else None

    def _finger_by_id(self, finger_id: int) -> dict | None:
        return next((finger for finger in self.db.list_fingers() if int(finger["id"]) == finger_id), None)

    def activation_hotkey(self) -> str:
        hotkey = HotkeyEdit.normalize_hotkey(self.db.get_setting("activation_hotkey", "ctrl+alt+f") or "ctrl+alt+f")
        return hotkey if self._is_valid_activation_hotkey(hotkey) else "ctrl+alt+f"

    def _is_valid_activation_hotkey(self, hotkey: str) -> bool:
        normalized = HotkeyEdit.normalize_hotkey(hotkey)
        if not normalized:
            return False
        try:
            import keyboard
            keyboard.parse_hotkey(normalized)
        except (TypeError, ValueError):
            return False
        return True

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
        if self.hotkey_paused:
            return
        hotkey = self.activation_hotkey()
        try:
            import keyboard
            self.hotkey_handle = keyboard.add_hotkey(hotkey, lambda: self.activation_requested.emit(), suppress=False)
        except Exception as exc:
            self.hotkey_handle = None
            message = tr(self.lang, "hotkey_registration_failed").format(error=exc)
            self.last_activity.setText(message)
            self._set_status_detail("warning", message)

    def unregister_activation_hotkey(self) -> None:
        if self.hotkey_handle is None:
            return
        try:
            import keyboard
            keyboard.remove_hotkey(self.hotkey_handle)
        except Exception:
            pass
        self.hotkey_handle = None

    def set_hotkey_paused(self, paused: bool) -> None:
        paused = bool(paused)
        if self.hotkey_paused == paused:
            return
        self.hotkey_paused = paused
        if paused:
            self.unregister_activation_hotkey()
            if self.scan_worker is not None:
                self.scan_worker.cancel()
            self.scan_prompt.hide()
            message = tr(self.lang, "hotkey_paused")
            self.last_activity.setText(message)
            self._append_activity(message)
            self._set_status_detail("warning", message)
        else:
            self.register_activation_hotkey()
            self._set_status_detail("", "")
        self.refresh_status()

    def start_triggered_scan(self) -> None:
        if self.hotkey_paused:
            return
        if self.scan_thread is not None:
            if self.scan_thread.isRunning():
                return
            self._scan_thread_finished(self.scan_thread, self.scan_worker)
        target_window_handle = int(ctypes.windll.user32.GetForegroundWindow() or 0)
        self._scan_had_action_results = False
        self.scan_prompt.show_prompt(self.lang)
        self.last_activity.setText(tr(self.lang, "scan_popup_waiting"))
        self._append_activity(_status_text(self.lang, "scan_started"))
        thread = QThread(self)
        worker = TriggeredFingerprintScan(
            self.db.path,
            self.lang,
            timer_scheduler=self.timer_manager.request_timer,
            target_window_handle=target_window_handle,
        )
        self.scan_thread = thread
        self.scan_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.matched.connect(self.on_scan_matched)
        worker.activity.connect(self.on_scan_activity)
        worker.action_result.connect(self.on_scan_action_result)
        worker.error.connect(self.on_scan_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(
            lambda current_thread=thread, current_worker=worker:
            self._scan_thread_finished(current_thread, current_worker)
        )
        thread.start()

    def on_scan_matched(self, _finger_name: str) -> None:
        message = tr(self.lang, "scan_recognized")
        self.last_activity.setText(message)
        self.scan_prompt.set_result(message)
        self.scan_prompt.close_later()

    def on_scan_action_result(self, result: dict) -> None:
        self._scan_had_action_results = True
        command_type = str(result.get("command_type") or "")
        label = action_labels(self.lang).get(command_type, command_type)
        status = str(result.get("status") or "")
        message = str(result.get("message") or "")
        if status == "success":
            entry = f"{tr(self.lang, 'executed')}: {label} — {message}"
        elif status == "skipped":
            entry = f"{tr(self.lang, 'action_result_skipped')}: {label}"
        elif status == "cancelled":
            entry = f"{tr(self.lang, 'action_result_cancelled')}: {label}"
        else:
            entry = f"{tr(self.lang, 'action_result_failed')}: {label}"
        self._append_activity(entry)

    def _scan_thread_finished(
        self,
        thread: QThread | None,
        _worker: TriggeredFingerprintScan | None,
    ) -> None:
        if thread is None:
            return
        if self.scan_thread is thread:
            self.scan_thread = None
            self.scan_worker = None
        thread.deleteLater()

    def _stop_scan_thread(self, timeout_ms: int = 17_000) -> None:
        worker = self.scan_worker
        thread = self.scan_thread
        if worker is not None:
            worker.cancel()
        if thread is None:
            return
        thread.quit()
        if thread.isRunning():
            thread.wait(timeout_ms)
        if not thread.isRunning() and self.scan_thread is thread:
            self.scan_thread = None
            self.scan_worker = None
            thread.deleteLater()

    def on_scan_activity(self, message: str) -> None:
        self.last_activity.setText(message)
        if not getattr(self, "_scan_had_action_results", False):
            self._append_activity(message)
        self._set_status_detail("success", message)
        self.scan_prompt.set_result(message)
        self.scan_prompt.close_later()

    def on_scan_error(self, message: str) -> None:
        self.last_activity.setText(message)
        if not getattr(self, "_scan_had_action_results", False):
            self._append_activity(message)
        self._set_status_detail("warning", message)
        self.scan_prompt.set_result(message, complete=message == tr(self.lang, "timeout"))
        self.scan_prompt.close_later(2400)

    def _current_autostart_mode(self) -> str:
        mode = self.db.get_setting("autostart_mode", "")
        if mode in {"disabled", "current_user", "current_user_tray"}:
            return mode
        return "current_user" if self.db.get_setting("autostart", "0") == "1" else "disabled"

    def _apply_autostart_mode(self, mode: str) -> None:
        import sys

        enabled = mode != "disabled"
        self.db.set_setting("autostart", "1" if enabled else "0")
        self.db.set_setting("autostart_mode", mode)
        setup_user_autostart(sys.executable, start_in_tray=mode == "current_user_tray") if enabled else remove_user_autostart()

    def toggle_autostart(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        mode = "current_user" if enabled else "disabled"
        if hasattr(self, "autostart_mode_combo"):
            self.autostart_mode_combo.blockSignals(True)
            self.autostart_mode_combo.setCurrentIndex(max(0, self.autostart_mode_combo.findData(mode)))
            self.autostart_mode_combo.blockSignals(False)
        self._apply_autostart_mode(mode)

    def change_autostart_mode(self) -> None:
        mode = str(self.autostart_mode_combo.currentData() or "disabled")
        enabled = mode != "disabled"
        self.autostart.blockSignals(True)
        self.autostart.setChecked(enabled)
        self.autostart.blockSignals(False)
        self._apply_autostart_mode(mode)

    def check_for_updates(self) -> None:
        if self.update_thread is not None and self.update_thread.isRunning():
            return
        self.check_updates_btn.setEnabled(False)
        self._set_label_opacity(self.update_status, 1.0)
        self._update_status_key = "checking_updates"
        self._update_status_kwargs = {}
        self.update_status.setText(tr(self.lang, self._update_status_key))
        self.update_thread = QThread(self)
        self.update_worker = _UpdateCheckWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.completed.connect(self._on_update_check_completed)
        self.update_worker.completed.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self._update_thread_finished)
        self.update_thread.start()

    @pyqtSlot(dict)
    def _on_update_check_completed(self, result: dict) -> None:
        if not result.get("ok"):
            self._show_update_status("update_check_failed", 4200, error=str(result.get("error", "")))
            return
        if result.get("no_releases"):
            self._show_update_status("update_no_releases", 3200)
            return
        latest = str(result.get("tag_name") or "")
        if _is_newer_version(latest, APP_VERSION):
            self._show_update_status(
                "update_available",
                5200,
                current=APP_VERSION,
                latest=latest,
                url=str(result.get("html_url") or LATEST_RELEASE_API_URL),
            )
        else:
            self._show_update_status("update_up_to_date", 3200, version=APP_VERSION)

    def _show_update_status(self, key: str, hold_ms: int, **values: str) -> None:
        self._update_status_key = key
        self._update_status_kwargs = values
        self._show_fading_label(self.update_status, tr(self.lang, key).format(**values), hold_ms)

    def _update_thread_finished(self) -> None:
        worker = self.update_worker
        thread = self.update_thread
        self.update_worker = None
        self.update_thread = None
        self.check_updates_btn.setEnabled(True)
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def open_monobank_support(self) -> None:
        QDesktopServices.openUrl(QUrl(MONOBANK_JAR_URL))

    def copy_trc20_address(self) -> None:
        QApplication.clipboard().setText(TRC20_WALLET_ADDRESS)
        self._show_fading_label(self.copy_status, tr(self.lang, "copied"), 1800)

    def _set_label_opacity(self, label: QLabel, opacity: float) -> None:
        effect = label.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(label)
            label.setGraphicsEffect(effect)
        effect.setOpacity(opacity)

    def _show_fading_label(self, label: QLabel, text: str, hold_ms: int) -> None:
        animation = self._fade_animations.get(label)
        if animation is not None:
            animation.stop()
        label.setText(text)
        self._set_label_opacity(label, 1.0)
        effect = label.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            return
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(520)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.finished.connect(lambda lbl=label, anim=animation: lbl.setText(" ") if self._fade_animations.get(lbl) is anim else None)
        self._fade_animations[label] = animation
        QTimer.singleShot(hold_ms, lambda lbl=label, anim=animation: anim.start() if self._fade_animations.get(lbl) is anim else None)

    def change_theme_key(self, theme_key: str) -> None:
        if not configure_theme(theme_key):
            return
        self.theme_key = theme_key
        self.db.set_setting("theme", theme_key)
        for button in self._theme_buttons:
            key = button.property("theme_key")
            color = {
                "light": "#F9FAFB",
                "onyx": "#000100",
                "graphite": "#323338",
                "dark": "#121A2F",
                "purple_gradient": "#2A123E",
                "blue_gradient": "#132B65",
            }.get(str(key), "#F9FAFB")
            active = key == theme_key
            if isinstance(button, ThemeSwatch):
                button.set_active(active)
            self._animate_swatch(button, 38 if active else 34)
        self._apply_theme_visuals()
        self.theme_changed.emit(theme_key)

    def _apply_theme_visuals(self) -> None:
        style = app_qss()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(style)
        self.setStyleSheet(style)
        self.fingers_table.verticalScrollBar().setStyleSheet(vertical_scrollbar_qss())
        self.title_bar.refresh_icons()
        for button in self.findChildren(QPushButton):
            icon_name = button.property("iconName")
            if icon_name:
                button.setIcon(icon(str(icon_name)))
        self.support_icon.setFixedSize(28, 28)
        self.support_icon.setPixmap(icon("support").pixmap(28, 28))
        self.monobank_btn.setIcon(icon("mono_button"))
        self.hotkey_chip.setStyleSheet(self._hotkey_chip_style())
        self.status_title.setStyleSheet(f"color:{THEME.subtle};")
        self.monitor_status.setStyleSheet(f"color:{THEME.subtle};")
        self.warning_text.setStyleSheet(f"color:{THEME.subtle};line-height:1.45;")
        self.autostart_mode_label.setStyleSheet(f"font-size:14px;color:{THEME.muted};")
        self.trc20_label.setStyleSheet(self._trc20_style())
        for index, tab in enumerate(self.tab_buttons):
            tab.set_active(index == self.stack.currentIndex())
        self._set_status_detail(self._last_status_mode, self._last_status_message)
        self._render_activity_log()
        self.refresh_fingers()
        self.scan_prompt.apply_theme()
        self.timer_notification.apply_theme()
        self.update()

    def _animate_swatch(self, button: ThemeSwatch, target_size: int) -> None:
        animation = self._swatch_animations.get(button)
        if animation is not None:
            animation.stop()
        animation = QVariantAnimation(self)
        animation.setDuration(160)
        animation.setStartValue(button.diameter())
        animation.setEndValue(target_size)
        animation.valueChanged.connect(lambda value, btn=button: btn.set_diameter(int(value)))
        self._swatch_animations[button] = animation
        animation.start()

    def change_language(self) -> None:
        self.lang = str(self.language_combo.currentData())
        self.db.set_setting("language", self.lang)
        self.retranslate()
        self.language_changed.emit(self.lang)

    def apply_theme(self, theme_key: str) -> None:
        self.change_theme_key(theme_key)

    def show_settings(self) -> None:
        self.set_tab(2)
        self._cancel_minimize_animation()
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def toggle_taskbar_visibility(self) -> None:
        if self.isHidden() or self.isMinimized():
            self._cancel_minimize_animation()
            self.showNormal()
            self.raise_()
            self.activateWindow()
        else:
            self.animate_minimize()

    def animate_minimize(self) -> None:
        if self.isMinimized() or self._minimize_animation is not None:
            return
        app = QApplication.instance()
        if app is None or app.platformName() == "offscreen":
            self.showMinimized()
            return

        self._minimize_restore_geometry = QRect(self.geometry())
        target = QRect(self._minimize_restore_geometry)
        target.translate(0, 18)

        group = QParallelAnimationGroup(self)
        geometry_animation = QPropertyAnimation(self, b"geometry", group)
        geometry_animation.setDuration(180)
        geometry_animation.setStartValue(self._minimize_restore_geometry)
        geometry_animation.setEndValue(target)
        geometry_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        opacity_animation = QPropertyAnimation(self, b"windowOpacity", group)
        opacity_animation.setDuration(180)
        opacity_animation.setStartValue(self.windowOpacity())
        opacity_animation.setEndValue(0.08)
        opacity_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        group.finished.connect(self._finish_animated_minimize)
        self._minimize_animation = group
        group.start()

    def _finish_animated_minimize(self) -> None:
        group = self._minimize_animation
        self._minimize_animation = None
        self.setUpdatesEnabled(False)
        if not self._minimize_restore_geometry.isNull():
            self.setGeometry(self._minimize_restore_geometry)
        self._native_minimize_passthrough = True
        self.showMinimized()
        QTimer.singleShot(120, self._finish_native_minimize_passthrough)
        self.setWindowOpacity(1.0)
        self.setUpdatesEnabled(True)
        self._minimize_restore_geometry = QRect()
        if group is not None:
            group.deleteLater()

    def _finish_native_minimize_passthrough(self) -> None:
        self._native_minimize_passthrough = False

    def _cancel_minimize_animation(self) -> None:
        group = self._minimize_animation
        if group is not None:
            group.stop()
            group.deleteLater()
            self._minimize_animation = None
            if not self._minimize_restore_geometry.isNull() and not self.isMinimized():
                self.setGeometry(self._minimize_restore_geometry)
            self._minimize_restore_geometry = QRect()
        self.setWindowOpacity(1.0)

    def nativeEvent(self, event_type, message):  # type: ignore[override]
        try:
            event_name = bytes(event_type).decode("ascii")
        except (TypeError, ValueError, UnicodeDecodeError):
            event_name = str(event_type)
        if event_name in {"windows_generic_MSG", "windows_dispatcher_MSG"}:
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0112 and int(msg.wParam) & 0xFFF0 == 0xF020:
                    if self._native_minimize_passthrough:
                        return False, 0
                    QTimer.singleShot(0, self.animate_minimize)
                    return True, 0
            except (TypeError, ValueError, OSError):
                pass
        return False, 0

    def shutdown(self) -> None:
        self.prepare_for_exit()
        self.close()

    def prepare_for_exit(self) -> None:
        self.allow_close = True
        self.unregister_activation_hotkey()
        self._stop_scan_thread()
        self.scan_prompt.hide()
        self.timer_notification.hide()
        if self.update_thread is not None and self.update_thread.isRunning():
            self.update_thread.quit()
            self.update_thread.wait(12000)

    def closeEvent(self, event) -> None:
        if self.allow_close:
            self.prepare_for_exit()
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()
