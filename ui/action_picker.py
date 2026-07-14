"""Searchable categorized action picker used by the finger wizard."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QModelIndex, QPoint, QSize, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QLineEdit,
    QListView,
    QStackedWidget,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.action_registry import ACTION_DEFINITIONS, ActionDefinition
from ui.i18n import tr
from ui.theme import THEME, icon


ACTION_ID_ROLE = Qt.ItemDataRole.UserRole + 1
CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 2
SEARCH_ROLE = Qt.ItemDataRole.UserRole + 3
HEADER_ROLE = Qt.ItemDataRole.UserRole + 4

CATEGORY_ORDER = ("basic", "macros", "system")


class _ActionPickerDelegate(QStyledItemDelegate):
    """Paint category rows as centered labels between separator lines."""

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:  # type: ignore[override]
        if not bool(index.data(HEADER_ROLE)):
            super().paint(painter, option, index)
            return

        painter.save()
        font = QFont(option.font)
        font.setPointSize(8)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(text)
        center_x = option.rect.center().x()
        text_left = center_x - text_width // 2
        text_right = center_x + text_width // 2
        line_y = option.rect.center().y()
        gap = 10
        margin = 12

        line_color = QColor(THEME.border)
        line_color.setAlpha(180)
        painter.setPen(QPen(line_color, 1))
        if text_left - gap > option.rect.left() + margin:
            painter.drawLine(option.rect.left() + margin, line_y, text_left - gap, line_y)
        if text_right + gap < option.rect.right() - margin:
            painter.drawLine(text_right + gap, line_y, option.rect.right() - margin, line_y)

        painter.setPen(QColor(THEME.subtle))
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option, index: QModelIndex) -> QSize:  # type: ignore[override]
        if bool(index.data(HEADER_ROLE)):
            return QSize(option.rect.width(), 30)
        return super().sizeHint(option, index)


class _ActionFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._query = ""

    def set_query(self, query: str) -> None:
        self._query = query.strip().casefold()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # type: ignore[override]
        if not self._query:
            return True
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(source_row, 0, source_parent)
        if not bool(index.data(HEADER_ROLE)):
            return self._query in str(index.data(SEARCH_ROLE) or "").casefold()

        category = index.data(CATEGORY_ROLE)
        for row in range(model.rowCount(source_parent)):
            candidate = model.index(row, 0, source_parent)
            if candidate.data(CATEGORY_ROLE) != category or bool(candidate.data(HEADER_ROLE)):
                continue
            if self._query in str(candidate.data(SEARCH_ROLE) or "").casefold():
                return True
        return False


class ActionPicker(QWidget):
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, lang: str = "uk", parent=None) -> None:
        super().__init__(parent)
        self.lang = lang
        self._definitions = list(ACTION_DEFINITIONS)
        self._current_index = 0

        self.display = QLineEdit(self)
        self.display.setReadOnly(True)
        self.display.setCursor(Qt.CursorShape.PointingHandCursor)
        self.display.setStyleSheet("padding-right: 38px;")
        self.display.installEventFilter(self)

        self.drop_button = QToolButton(self)
        self.drop_button.setIcon(icon("dropdown_list"))
        self.drop_button.setIconSize(self.drop_button.iconSize())
        self.drop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drop_button.setStyleSheet(
            "QToolButton{background:transparent;border:0;padding:0;}"
        )
        self.drop_button.clicked.connect(self.show_popup)

        self.popup = QFrame(
            None,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.popup.setObjectName("actionPickerPopup")
        self.popup.setStyleSheet(
            f"""
            QFrame#actionPickerPopup {{
                background: {THEME.surface};
                border: 1px solid {THEME.input_border};
                border-radius: 10px;
            }}
            QLineEdit {{
                background: {THEME.surface};
                color: {THEME.text};
                border: 1px solid {THEME.input_border};
                border-radius: 8px;
                min-height: 34px;
                padding: 0 10px;
            }}
            QListView {{
                background: {THEME.surface};
                color: {THEME.text};
                border: 0;
                outline: 0;
            }}
            QListView::item {{
                min-height: 32px;
                padding: 3px 10px;
                border-radius: 6px;
            }}
            QListView::item:selected {{
                background: {THEME.selected_bg};
                color: {THEME.text};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 3px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {THEME.scrollbar};
                border: 0;
                border-radius: 1px;
                min-height: 32px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
                border: 0;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: transparent;
                border: 0;
                width: 0;
                height: 0;
            }}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
                background: transparent;
                border: 0;
                width: 0;
                height: 0;
            }}
            QAbstractScrollArea::corner {{ background: transparent; border: 0; }}
            """
        )
        popup_layout = QVBoxLayout(self.popup)
        popup_layout.setContentsMargins(8, 8, 8, 8)
        popup_layout.setSpacing(6)

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_actions)
        self.search.installEventFilter(self)
        popup_layout.addWidget(self.search)

        self.model = QStandardItemModel(self)
        self.proxy = _ActionFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.list_view = QListView()
        self.list_view.setModel(self.proxy)
        self.list_view.setItemDelegate(_ActionPickerDelegate(self.list_view))
        self.list_view.setUniformItemSizes(False)
        self.list_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list_view.clicked.connect(self._activate_index)
        self.list_view.installEventFilter(self)

        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color:{THEME.muted};border:0;")

        self.results_stack = QStackedWidget()
        self.results_stack.addWidget(self.list_view)
        self.results_stack.addWidget(self.empty_label)
        popup_layout.addWidget(self.results_stack)

        self._rebuild_model()
        self._update_display()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.display.setGeometry(self.rect())
        self.drop_button.setGeometry(max(0, self.width() - 36), 0, 34, self.height())

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self.display and event.type() == QEvent.Type.MouseButtonPress:
            self.show_popup()
            return True
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)

        key = event.key()
        if key == Qt.Key.Key_Escape and self.popup.isVisible():
            self.popup.hide()
            self.setFocus()
            return True
        if watched is self.search and key == Qt.Key.Key_Down:
            self._select_first_action()
            self.list_view.setFocus()
            return True
        if watched in (self.search, self.list_view) and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.list_view.currentIndex()
            if not index.isValid():
                index = self._first_action_index()
            self._activate_index(index)
            return True
        return super().eventFilter(watched, event)

    def show_popup(self) -> None:
        self.search.clear()
        popup_width = max(self.width(), 360)
        popup_height = min(360, 58 + self.proxy.rowCount() * 38)
        self.popup.setFixedSize(popup_width, max(210, popup_height))
        position = self.mapToGlobal(QPoint(0, self.height() + 4))
        screen = QApplication.screenAt(position)
        if screen is not None and position.y() + self.popup.height() > screen.availableGeometry().bottom():
            position = self.mapToGlobal(QPoint(0, -self.popup.height() - 4))
        self.popup.move(position)
        self.popup.show()
        self.popup.raise_()
        self.search.setFocus()

    def currentData(self):
        if not self._definitions:
            return None
        return self._definitions[self._current_index].command_type

    def currentIndex(self) -> int:
        return self._current_index

    def findData(self, command_type: str) -> int:
        for index, definition in enumerate(self._definitions):
            if definition.command_type == command_type:
                return index
        return -1

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < len(self._definitions) or index == self._current_index:
            return
        self._current_index = index
        self._update_display()
        self.currentIndexChanged.emit(index)

    def set_language(self, lang: str) -> None:
        self.lang = lang
        self._rebuild_model()
        self._update_display()

    def filtered_action_ids(self) -> list[str]:
        result: list[str] = []
        for row in range(self.proxy.rowCount()):
            action_id = self.proxy.index(row, 0).data(ACTION_ID_ROLE)
            if action_id:
                result.append(str(action_id))
        return result

    def set_search_text(self, text: str) -> None:
        self.search.setText(text)

    def _rebuild_model(self) -> None:
        self.model.clear()
        definitions_by_category: dict[str, list[ActionDefinition]] = {}
        for definition in self._definitions:
            definitions_by_category.setdefault(definition.category, []).append(definition)

        for category in CATEGORY_ORDER:
            definitions = definitions_by_category.get(category, [])
            if not definitions:
                continue
            header = QStandardItem(tr(self.lang, f"action_category_{category}").upper())
            header.setData(category, CATEGORY_ROLE)
            header.setData(True, HEADER_ROLE)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setForeground(QColor(THEME.muted))
            header_font = QFont()
            header_font.setPointSize(8)
            header_font.setWeight(QFont.Weight.DemiBold)
            header.setFont(header_font)
            self.model.appendRow(header)

            for definition in definitions:
                label = tr(self.lang, definition.label_key)
                item = QStandardItem(label)
                item.setData(definition.command_type, ACTION_ID_ROLE)
                item.setData(category, CATEGORY_ROLE)
                item.setData(False, HEADER_ROLE)
                item.setData(
                    " ".join((label, definition.command_type, *definition.keywords)),
                    SEARCH_ROLE,
                )
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.model.appendRow(item)
        self.search.setPlaceholderText(tr(self.lang, "action_search"))
        self.empty_label.setText(tr(self.lang, "action_not_found"))
        self.proxy.invalidateFilter()

    def _filter_actions(self, text: str) -> None:
        self.proxy.set_query(text)
        self.results_stack.setCurrentWidget(
            self.list_view if self.filtered_action_ids() else self.empty_label
        )
        self._select_first_action()

    def _first_action_index(self) -> QModelIndex:
        for row in range(self.proxy.rowCount()):
            index = self.proxy.index(row, 0)
            if index.data(ACTION_ID_ROLE):
                return index
        return QModelIndex()

    def _select_first_action(self) -> None:
        index = self._first_action_index()
        if index.isValid():
            self.list_view.setCurrentIndex(index)

    def _activate_index(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        command_type = index.data(ACTION_ID_ROLE)
        if not command_type:
            return
        action_index = self.findData(str(command_type))
        if action_index >= 0:
            self.setCurrentIndex(action_index)
        self.popup.hide()

    def _update_display(self) -> None:
        if not self._definitions:
            self.display.clear()
            return
        definition = self._definitions[self._current_index]
        self.display.setText(tr(self.lang, definition.label_key))
