from pathlib import Path

from PyQt6.QtGui import QColor

from ui.theme import (
    THEME,
    configure_theme,
    icon_path,
    qcolor,
    vertical_scrollbar_qss,
)


def test_dark_theme_uses_reference_tokens_and_dark_assets():
    try:
        assert configure_theme("dark")
        assert THEME.bg == "#243044"
        assert THEME.surface == "#4B5563"
        assert THEME.title_main == "#1A2338"
        assert THEME.tab_active == "#334155"
        assert THEME.tab_inactive == "#1E2A3D"
        assert THEME.selected_bg == "#1E2F4D"
        assert THEME.primary == "#1D74F7"
        assert THEME.subtle == "#9CA3AF"
        assert THEME.disabled_bg == "#3A4759"

        scan_icon = Path(icon_path("icon_scan"))
        inactive_next = Path(icon_path("inactive_next"))
        assert scan_icon.parent.name == "dark"
        assert inactive_next.parent.name == "dark"
        assert "stroke=\"#0B4721\"" in scan_icon.read_text(encoding="utf-8")
    finally:
        configure_theme("light")


def test_unknown_theme_does_not_replace_current_theme():
    try:
        configure_theme("dark")
        assert not configure_theme("not-a-theme")
        assert THEME.key == "dark"
    finally:
        configure_theme("light")


def test_onyx_theme_uses_reference_tokens_and_complete_assets():
    try:
        assert configure_theme("onyx")
        assert THEME.bg == "#1A1A1D"
        assert THEME.surface == "#1E1E22"
        assert THEME.settings_surface == "#1E1E22"
        assert THEME.title_main == "#111113"
        assert THEME.tab_active == "#1E1E22"
        assert THEME.tab_active_text == "#6AA6FF"
        assert THEME.tab_inactive == "#27272B"
        assert THEME.tab_inactive_text == "#6B7280"
        assert THEME.selected_bg == "#BA303031"
        selected = QColor(THEME.selected_bg)
        assert selected.getRgb() == (48, 48, 49, 186)
        assert THEME.action_button_bg == "#222226"
        assert THEME.disabled_bg == "#1B1F22"
        assert THEME.disabled_text == "#515151"
        assert THEME.trc_bg == "#252529"

        for icon_name in (
            "checkbox_checked",
            "close_titlebar",
            "close_wizard_fixed",
            "check_version_white",
            "mono_button",
            "inactive_next",
        ):
            assert Path(icon_path(icon_name)).parent.name == "onyx"
    finally:
        configure_theme("light")


def test_graphite_theme_uses_reference_tokens_and_complete_assets():
    try:
        assert configure_theme("graphite")
        assert THEME.bg == "#323339"
        assert THEME.surface == "#3C3D46"
        assert THEME.settings_surface == "#3C3D46"
        assert THEME.title_main == "#1C1D21"
        assert THEME.title_wizard == "#28292F"
        assert THEME.tab_active == "#3C3D46"
        assert THEME.tab_active_text == "#1D74F7"
        assert THEME.tab_inactive == "#2C2D35"
        assert THEME.tab_inactive_text == "#8E8F9E"
        assert THEME.wizard_capture_surface == "#3C3D46"
        assert THEME.wizard_done_surface == "#3C3D46"
        assert THEME.warning_bg == "#2C2D35"
        assert THEME.status_log_surface == "#2C2D35"
        assert THEME.selected_bg == "#E341434C"
        selected = QColor(THEME.selected_bg)
        assert selected.getRgb() == (65, 67, 76, 227)
        assert THEME.action_button_bg == "#3C3D46"
        assert THEME.disabled_bg == "#343439"
        assert THEME.trc_bg == "#464750"

        for icon_name in (
            "checkbox_checked",
            "close_titlebar",
            "close_wizard_fixed",
            "check_version_white",
            "mono_button",
            "inactive_next",
        ):
            assert Path(icon_path(icon_name)).parent.name == "graphite"
    finally:
        configure_theme("light")


def test_blue_gradient_theme_uses_reference_tokens_and_complete_assets():
    try:
        assert configure_theme("blue_gradient")
        assert THEME.bg == "#0B1120"
        assert THEME.title_main == "#060C1A"
        assert THEME.tab_active == "rgba(255,255,255,46)"
        assert THEME.tab_active_text == "#60A5FA"
        assert THEME.tab_inactive == "rgba(255,255,255,15)"
        assert THEME.tab_inactive_text == "rgba(224,231,255,128)"
        assert THEME.surface == "rgba(255,255,255,20)"
        assert THEME.table_header_bg == "rgba(255,255,255,10)"
        assert THEME.popup_surface == "#263A6C"
        assert THEME.scrollbar == "#3A4B76"
        assert THEME.scrollbar_track == "#1E3A8A"
        scrollbar_style = vertical_scrollbar_qss()
        assert "background: #1E3A8A" in scrollbar_style
        assert "background: #3A4B76" in scrollbar_style
        assert qcolor(THEME.muted).getRgb() == (224, 231, 255, 128)
        assert THEME.settings_input_border == "#95BFFF"
        assert THEME.selected_bg == "#C422376F"
        assert QColor(THEME.selected_bg).getRgb() == (34, 55, 111, 196)
        assert "#0B1120" in THEME.canvas_brush
        assert "#1E3A8A" in THEME.canvas_brush
        assert "#2563EB" in THEME.primary_brush
        assert "#1E40AF" in THEME.primary_brush
        assert THEME.is_gradient

        for icon_name in (
            "checkbox_checked",
            "close_titlebar",
            "close_wizard_fixed",
            "check_version_white",
            "mono_button",
            "inactive_next",
            "icon_scan",
            "icon_done",
        ):
            assert Path(icon_path(icon_name)).parent.name == "blue"
        support_svg = Path(icon_path("support")).read_text(encoding="utf-8")
        assert 'width="28"' in support_svg
        assert 'fill-opacity="0.08"' in support_svg
        assert 'stroke="#E0E7FF"' in support_svg
    finally:
        configure_theme("light")


def test_purple_gradient_theme_uses_reference_tokens_and_complete_assets():
    try:
        assert configure_theme("purple_gradient")
        assert THEME.bg == "#10152A"
        assert THEME.title_main == "#060910"
        assert THEME.tab_active == "rgba(255,255,255,46)"
        assert THEME.tab_active_text == "#C084FC"
        assert THEME.tab_inactive == "rgba(255,255,255,20)"
        assert qcolor(THEME.tab_inactive_text).getRgb() == (245, 240, 250, 115)
        assert THEME.surface == "rgba(255,255,255,23)"
        assert THEME.table_header_bg == "rgba(255,255,255,10)"
        assert THEME.settings_input_border == "rgba(209,213,219,77)"
        assert THEME.popup_surface == "#482957"
        assert THEME.scrollbar == "rgba(255,255,255,31)"
        assert THEME.scrollbar_track == "#3D0E52"
        assert THEME.selected_bg == "#BD42216A"
        assert QColor(THEME.selected_bg).getRgb() == (66, 33, 106, 189)
        assert qcolor(THEME.selection_border).getRgb() == (29, 116, 247, 115)
        assert THEME.completion_action_text == "#C084FC"
        assert "#10152A" in THEME.canvas_brush
        assert "#3D0E52" in THEME.canvas_brush
        assert "#7C3AED" in THEME.primary_brush
        assert "#C026D3" in THEME.primary_brush
        assert THEME.is_gradient

        for icon_name in (
            "checkbox_checked",
            "close_titlebar",
            "close_wizard_fixed",
            "check_version_white",
            "mono_button",
            "inactive_next",
            "icon_scan",
            "icon_done",
        ):
            assert Path(icon_path(icon_name)).parent.name == "purple"
        support_svg = Path(icon_path("support")).read_text(encoding="utf-8")
        assert 'width="28"' in support_svg
        assert 'stroke="#F5F0FA"' in support_svg
        blue_assets = {path.name for path in (Path(icon_path("support")).parents[1] / "blue").glob("*.svg")}
        purple_assets = {path.name for path in Path(icon_path("support")).parent.glob("*.svg")}
        assert purple_assets == blue_assets
    finally:
        configure_theme("light")
