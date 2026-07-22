from __future__ import annotations

import ctypes
import getpass
import sys
from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox, QStyle

from core.database import Database
from services.autostart import bootstrap_distribution, remove_user_autostart
from ui.main_window import MainWindow
from ui.tray import FingerprintTray
from ui.i18n import tr


ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.ico"
APP_USER_MODEL_ID = "FingerprintLauncher.Desktop"
SINGLE_INSTANCE_NAME = f"FingerprintLauncher-{getpass.getuser()}"


class SingleInstance(QObject):
    activation_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._mutex_handle = None
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept_connections)

    def acquire_or_notify(self) -> bool:
        if sys.platform == "win32":
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            handle = kernel32.CreateMutexW(
                None,
                False,
                f"Local\\{SINGLE_INSTANCE_NAME}-Mutex",
            )
            if not handle:
                return False
            if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                kernel32.CloseHandle(handle)
                self._notify_existing()
                return False
            self._mutex_handle = handle

        if self.server.listen(SINGLE_INSTANCE_NAME):
            return True

        QLocalServer.removeServer(SINGLE_INSTANCE_NAME)
        return self.server.listen(SINGLE_INSTANCE_NAME)

    @staticmethod
    def _notify_existing() -> None:
        socket = QLocalSocket()
        socket.connectToServer(SINGLE_INSTANCE_NAME)
        if socket.waitForConnected(750):
            socket.write(b"toggle")
            socket.flush()
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()

    def _accept_connections(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if socket is None:
                continue
            socket.waitForReadyRead(100)
            if bytes(socket.readAll()) == b"toggle":
                self.activation_requested.emit()
            socket.disconnectFromServer()
            socket.deleteLater()

    def close(self) -> None:
        self.server.close()
        if self._mutex_handle and sys.platform == "win32":
            ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
            self._mutex_handle = None


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


def configure_autostart(db: Database) -> list[str]:
    """Apply the saved startup preference and migrate the old implicit default."""
    setting = db.get_setting("autostart")
    if setting == "1":
        mode = db.get_setting("autostart_mode", "current_user") or "current_user"
        return bootstrap_distribution(start_in_tray=mode == "current_user_tray")
    if setting is None:
        db.set_setting("autostart", "0")
        db.set_setting("autostart_mode", "disabled")
        try:
            remove_user_autostart()
        except Exception as exc:
            return [f"Autostart cleanup failed: {exc}"]
    return []


def main() -> int:
    hide_console_window()
    set_windows_app_id()
    bootstrap_errors: list[str] = []
    with Database() as db:
        lang = db.get_setting("language", "uk") or "uk"
        bootstrap_errors = configure_autostart(db)

    app = QApplication(sys.argv)
    configure_app_font(app)
    app.setQuitOnLastWindowClosed(False)
    single_instance = SingleInstance()
    if not single_instance.acquire_or_notify():
        return 0
    app.aboutToQuit.connect(single_instance.close)

    errors = [*bootstrap_errors, *startup_checks(lang)]
    if errors:
        QMessageBox.warning(None, "FingerprintLauncher", "\n".join(errors))

    icon = load_app_icon(app)
    app.setWindowIcon(icon)

    window = MainWindow()
    window.setWindowIcon(icon)
    tray = FingerprintTray(icon, lang=window.lang)
    tray.settings_action.triggered.connect(window.show_settings)
    tray.pause_toggled.connect(window.set_hotkey_paused)
    tray.pause_toggled.connect(tray.set_paused)
    tray.bind_timer_manager(window.timer_manager)
    single_instance.activation_requested.connect(window.toggle_taskbar_visibility)
    window.language_changed.connect(tray.set_language)
    window.theme_changed.connect(tray.set_theme)
    app.aboutToQuit.connect(window.prepare_for_exit)
    tray.quit_action.triggered.connect(window.shutdown)
    tray.quit_action.triggered.connect(app.quit)
    tray.show()

    start_in_tray = "--tray" in sys.argv
    if not start_in_tray:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
