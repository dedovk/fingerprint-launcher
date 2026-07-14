from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMessageBox, QStyle

from core.database import Database
from services.autostart import bootstrap_distribution
from ui.main_window import MainWindow
from ui.tray import FingerprintTray
from ui.i18n import tr


ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.ico"
APP_USER_MODEL_ID = "FingerprintLauncher.Desktop"


def hide_console_window() -> None:
    """Hide the Win32 console window that python.exe opens in development.

    In distribution builds (Nuitka + --windows-console-mode=disable) there is
    no console at all. When developers run `python main.py` the console flashes
    briefly then disappears so logs are no longer mixed with the GUI.
    """
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
    except Exception:
        pass


def set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID)
    except Exception:
        pass


def startup_checks(lang: str = "uk") -> list[str]:
    errors: list[str] = []
    if sys.platform == "win32" and sys.getwindowsversion().major < 10:
        errors.append(tr(lang, "startup_windows_version"))
    if sys.platform == "win32":
        try:
            ctypes.WinDLL("winbio.dll")
        except OSError:
            errors.append(tr(lang, "startup_wbf_missing"))
    return errors


def load_app_icon(app: QApplication) -> QIcon:
    icon = QIcon(str(ICON_PATH))
    if not icon.isNull():
        return icon
    fallback = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    if not fallback.isNull():
        return fallback
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("#2563eb"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("white"))
    painter.drawText(pixmap.rect(), 0x84, "FL")
    painter.end()
    return QIcon(pixmap)


def configure_app_font(app: QApplication) -> None:
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)


def main() -> int:
    hide_console_window()
    set_windows_app_id()
    bootstrap_errors: list[str] = []
    with Database() as db:
        lang = db.get_setting("language", "uk") or "uk"
        if db.get_setting("autostart", "1") == "1":
            bootstrap_errors = bootstrap_distribution()

    app = QApplication(sys.argv)
    configure_app_font(app)
    app.setQuitOnLastWindowClosed(False)

    errors = [*bootstrap_errors, *startup_checks(lang)]
    if errors:
        QMessageBox.warning(None, "FingerprintLauncher", "\n".join(errors))

    icon = load_app_icon(app)
    app.setWindowIcon(icon)

    window = MainWindow()
    window.setWindowIcon(icon)
    tray = FingerprintTray(icon, lang=window.lang)
    tray.settings_action.triggered.connect(window.show_settings)
    window.language_changed.connect(tray.set_language)
    window.theme_changed.connect(tray.set_theme)
    tray.quit_action.triggered.connect(window.shutdown)
    tray.quit_action.triggered.connect(app.quit)
    tray.show()

    start_in_tray = "--tray" in sys.argv
    if not start_in_tray:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
