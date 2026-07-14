from pathlib import Path

from PyQt6.QtGui import QColor

from ui.theme import THEME, configure_theme, icon_path


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
