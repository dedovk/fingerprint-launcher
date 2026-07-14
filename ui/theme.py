"""Theme and UI helpers for the redesigned interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QComboBox, QGraphicsOpacityEffect, QListView, QWidget
from PyQt6.QtGui import QIcon


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"


@dataclass(frozen=True)
class ThemeSpec:
    key: str
    bg: str
    surface: str
    settings_surface: str
    action_row_bg: str
    action_button_bg: str
    title_main: str
    title_wizard: str
    text: str
    muted: str
    subtle: str
    border: str
    input_border: str
    settings_input_border: str
    border_focus: str
    primary: str
    primary_hover: str
    primary_2: str
    secondary: str
    secondary_text: str
    dark_button: str
    disabled_bg: str
    disabled_text: str
    success: str
    danger: str
    selected_bg: str
    selected_action_text: str
    scrollbar: str
    tab_bar: str
    tab_active: str
    tab_active_text: str
    tab_inactive: str
    tab_inactive_text: str
    checkbox_bg: str
    checkbox_border: str
    warning_bg: str
    success_bg: str
    trc_bg: str
    trc_text: str
    trc_border: str


THEME_SPECS = {
    "light": ThemeSpec(
        key="light", bg="#F5F5F7", surface="#FFFFFF",
        settings_surface="#FFFFFF", action_row_bg="#FFFFFF", action_button_bg="#EEEEF8",
        title_main="#202020", title_wizard="#EBEBEE",
        text="#1A1A2E", muted="#6B7280", subtle="#6B7280",
        border="#E4E4E7", input_border="#D8DCE3", settings_input_border="#D8DCE3", border_focus="#A7CEFF",
        primary="#1D74F7", primary_hover="#1767DE", primary_2="#2E84F1",
        secondary="#EEEEF8", secondary_text="#1A1A2E", dark_button="#3C3D3E",
        disabled_bg="#EEEEF8", disabled_text="#6B7280",
        success="#16A34A", danger="#FF0004", selected_bg="#EFF6FF",
        selected_action_text="#1D74F7",
        scrollbar="#D9D9D9", tab_bar="#F5F5F7", tab_active="#FFFFFF", tab_active_text="#1A1A2E",
        tab_inactive="#E8E8EC", tab_inactive_text="#6B7280", checkbox_bg="#FFFFFF", checkbox_border="#CBD1DB",
        warning_bg="#E9E9EE", success_bg="#F0FDF4",
        trc_bg="#EEEEF8", trc_text="#1A1A2E", trc_border="#E4E4E7",
    ),
    "dark": ThemeSpec(
        key="dark", bg="#243044", surface="#4B5563",
        settings_surface="#4B5563", action_row_bg="#4B5563", action_button_bg="#243044",
        title_main="#1A2338", title_wizard="#1A2338",
        text="#F9FAFB", muted="#BABABF", subtle="#9CA3AF",
        border="#656565", input_border="#656565", settings_input_border="#656565", border_focus="#1D74F7",
        primary="#1D74F7", primary_hover="#1767DE", primary_2="#2E84F1",
        secondary="#243044", secondary_text="#F9FAFB", dark_button="#1F2937",
        disabled_bg="#3A4759", disabled_text="rgba(255,255,255,128)",
        success="#16A34A", danger="#FF0004", selected_bg="#1E2F4D",
        selected_action_text="#6BA6FF",
        scrollbar="#656565", tab_bar="#243044", tab_active="#334155", tab_active_text="#1D74F7",
        tab_inactive="#1E2A3D", tab_inactive_text="#BABABF", checkbox_bg="#FFFFFF", checkbox_border="#D1D5DB",
        warning_bg="#4B5563", success_bg="#4B5563",
        trc_bg="#EEEEF8", trc_text="#1A1A2E", trc_border="#E4E4E7",
    ),
    "onyx": ThemeSpec(
        key="onyx", bg="#1A1A1D", surface="#1E1E22",
        settings_surface="#1E1E22", action_row_bg="#1E1E22", action_button_bg="#222226",
        title_main="#111113", title_wizard="#111113",
        text="#F5F5F5", muted="#6B7280", subtle="#6B7280",
        border="#2E2E32", input_border="#2E2E32", settings_input_border="rgba(131,131,131,163)", border_focus="#1D74F7",
        primary="#1D74F7", primary_hover="#1767DE", primary_2="#2E84F1",
        secondary="#252529", secondary_text="#F9FAFB", dark_button="#3C3D3E",
        disabled_bg="#1B1F22", disabled_text="#515151",
        success="#16A34A", danger="#FF0004", selected_bg="#BA303031",
        selected_action_text="#6AA6FF",
        scrollbar="#6B7280", tab_bar="#1A1A1D", tab_active="#1E1E22", tab_active_text="#6AA6FF",
        tab_inactive="#27272B", tab_inactive_text="#6B7280", checkbox_bg="#FFFFFF", checkbox_border="#D1D5DB",
        warning_bg="#1E1E22", success_bg="#1E1E22",
        trc_bg="#252529", trc_text="#F5F5F5", trc_border="#2E2E32",
    ),
}


class Theme:
    font = "Inter"
    mono_font = "Consolas"

    def __init__(self) -> None:
        self.apply(THEME_SPECS["light"])

    def apply(self, spec: ThemeSpec) -> None:
        for name, value in spec.__dict__.items():
            setattr(self, name, value)


THEME = Theme()


def configure_theme(theme_key: str) -> bool:
    spec = THEME_SPECS.get(theme_key)
    if spec is None:
        return False
    THEME.apply(spec)
    return True


def icon_path(name: str, theme: str | None = None) -> str:
    theme_key = theme or THEME.key
    themed_path = ASSETS_DIR / theme_key / f"{name}.svg"
    if themed_path.exists():
        return str(themed_path)
    return str(ASSETS_DIR / "light" / f"{name}.svg")


def icon(name: str, theme: str | None = None) -> QIcon:
    return QIcon(icon_path(name, theme))


class StableComboBox(QComboBox):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._covered_widgets: list[QWidget] = []
        self._covered_states: list[tuple[QWidget, bool, object | None]] = []

    def set_covered_widgets(self, widgets: list[QWidget]) -> None:
        self._covered_widgets = widgets

    def showPopup(self) -> None:  # type: ignore[override]
        self._covered_states = []
        for widget in self._covered_widgets:
            self._covered_states.append((widget, widget.isEnabled(), widget.graphicsEffect()))
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)
            widget.setEnabled(False)
        super().showPopup()

    def hidePopup(self) -> None:  # type: ignore[override]
        super().hidePopup()
        for widget, was_enabled, previous_effect in self._covered_states:
            widget.setGraphicsEffect(previous_effect)
            widget.setEnabled(was_enabled)
        self._covered_states = []


def prepare_combo_popup(combo: QComboBox) -> None:
    view = QListView(combo)
    view.setUniformItemSizes(True)
    view.setAutoFillBackground(True)
    view.viewport().setAutoFillBackground(True)
    combo.setView(view)
    combo.setMaxVisibleItems(8)


def app_qss() -> str:
    t = THEME
    return f"""
        QWidget {{
            background: {t.bg};
            color: {t.text};
            font-family: "{t.font}", "Segoe UI", sans-serif;
            font-size: 14px;
        }}
        QMainWindow, QDialog {{
            background: {t.bg};
        }}
        QLabel {{
            background: transparent;
        }}
        QLabel[role="muted"] {{
            color: {t.muted};
        }}
        QLabel[role="sectionTitle"] {{
            color: {t.text};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel[role="fieldLabel"], QHeaderView::section {{
            color: {t.muted};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.88px;
        }}
        QLabel[role="mono"], QLineEdit[role="mono"], QTableWidget::item[role="mono"] {{
            font-family: "{t.mono_font}", monospace;
        }}
        QLineEdit, QComboBox {{
            background: {t.surface};
            color: {t.text};
            border: 1px solid {t.input_border};
            border-radius: 10px;
            min-height: 36px;
            padding: 0 12px;
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 1px solid {t.primary};
        }}
        QComboBox[role="settingsInput"] {{
            border: 1px solid {t.settings_input_border};
        }}
        QComboBox::drop-down {{
            border: 0;
            width: 34px;
        }}
        QComboBox::down-arrow {{
            image: url({icon_path("dropdown_list").replace("\\", "/")});
            width: 12px;
            height: 12px;
            margin-right: 12px;
        }}
        QComboBox QAbstractItemView {{
            background: {t.surface};
            color: {t.text};
            border: 1px solid {t.input_border};
            border-radius: 8px;
            padding: 4px;
            outline: 0;
            selection-background-color: {t.selected_bg};
            selection-color: {t.text};
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 28px;
            padding: 6px 10px;
            background: {t.surface};
        }}
        QPushButton {{
            border-radius: 10px;
            min-height: 28px;
            padding: 0 14px;
            font-size: 14px;
            font-weight: 500;
        }}
        QPushButton[kind="primary"] {{
            background: {t.primary};
            color: #ffffff;
            border: 1px solid {t.primary};
        }}
        QPushButton[kind="primary"]:hover {{
            background: {t.primary_hover};
        }}
        QPushButton[kind="secondary"] {{
            background: {t.secondary};
            color: {t.secondary_text};
            border: 1px solid {t.border};
        }}
        QPushButton[kind="actionSecondary"] {{
            background: {t.action_button_bg};
            color: {t.secondary_text};
            border: 1px solid {t.border};
        }}
        QPushButton[kind="ghost"] {{
            background: {t.bg};
            color: {t.muted};
            border: 0;
        }}
        QPushButton[kind="dark"] {{
            background: {t.dark_button};
            color: #ffffff;
            border: 1px solid {t.dark_button};
        }}
        QPushButton:disabled {{
            background: {t.disabled_bg};
            color: {t.disabled_text};
            border: 1px solid {t.border};
        }}
        QPushButton[kind="ghost"]:disabled {{
            background: {t.bg};
            color: {t.muted};
            border: 0;
        }}
        QFrame[role="card"] {{
            background: {t.surface};
            border: 1px solid {t.border};
            border-radius: 14px;
        }}
        QFrame[role="settingsCard"] {{
            background: {t.settings_surface};
            border: 1px solid {t.border};
            border-radius: 14px;
        }}
        QFrame[role="statusLog"] {{
            background: {t.surface};
            border: 1px solid {t.border};
            border-radius: 14px;
        }}
        QFrame[role="actionRow"] {{
            background: {t.action_row_bg};
            border: 1px solid {t.border};
            border-radius: 14px;
        }}
        QFrame[role="footer"] {{
            background: {t.bg};
            border-top: 1px solid {t.border};
        }}
        QFrame[role="tabBar"] {{
            background: {t.tab_bar};
            border: 0;
        }}
        QFrame[role="separator"] {{
            background: {t.border};
            border: 0;
        }}
        QFrame[role="titleMain"] {{
            background: {t.title_main};
        }}
        QFrame[role="titleWizard"] {{
            background: {t.title_wizard};
        }}
        QLabel[role="mainTitle"] {{
            color: #ffffff;
            font-size: 12px;
            font-weight: 600;
        }}
        QLabel[role="wizardTitle"] {{
            color: {t.text};
            font-size: 12px;
            font-weight: 600;
        }}
        QPushButton[role="windowButton"] {{
            background: transparent;
            color: #ffffff;
            border: 0;
            min-width: 28px;
            max-width: 28px;
            min-height: 28px;
            max-height: 28px;
            padding: 0;
            font-family: "Segoe UI", sans-serif;
            font-size: 16px;
            font-weight: 400;
        }}
        QPushButton[role="wizardWindowButton"] {{
            background: transparent;
            color: {t.muted};
            border: 0;
            min-width: 25px;
            max-width: 25px;
            min-height: 25px;
            max-height: 25px;
            padding: 0;
            border-radius: 9px;
            font-family: "Segoe UI", sans-serif;
            font-size: 16px;
            font-weight: 400;
        }}
        QTableWidget {{
            background: {t.bg};
            border: 0;
            gridline-color: {t.border};
            selection-background-color: {t.selected_bg};
            selection-color: {t.text};
            outline: 0;
        }}
        QTableWidget::item {{
            border: 0;
            padding-left: 20px;
        }}
        QTableWidget::item:selected {{
            background: {t.selected_bg};
            color: {t.text};
            border-top: 1px solid {t.border_focus};
            border-bottom: 1px solid {t.border_focus};
        }}
        QHeaderView::section {{
            background: {t.bg};
            border: 0;
            border-bottom: 1px solid {t.border};
            padding-left: 20px;
        }}
        QScrollArea {{
            background: transparent;
            border: 0;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 3px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {t.scrollbar};
            border-radius: 1px;
            min-height: 36px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
            border: 0;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
            width: 0;
            background: transparent;
            border: 0;
        }}
        QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
            background: transparent;
            border: 0;
            width: 0;
            height: 0;
        }}
        QScrollBar:horizontal {{
            height: 0;
            background: transparent;
        }}
        QScrollBar::handle:horizontal, QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
            border: 0;
        }}
        QCheckBox {{
            background: transparent;
            spacing: 12px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1.6px solid {t.checkbox_border};
            border-radius: 4px;
            background: {t.checkbox_bg};
        }}
        QCheckBox::indicator:checked {{
            background: {t.primary};
            border-color: {t.primary};
            image: url({icon_path("checkbox_checked").replace("\\", "/")});
        }}
    """
