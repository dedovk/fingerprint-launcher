"""Windows autostart helpers.

Historically this module also installed a Windows Service that owned the
fingerprint sensor. That design has been removed: WinBio identify under
LocalSystem only works for credential-provider scenarios (lock screen, UAC),
not background monitoring. The whole app now runs as an ordinary user-space
process and is started at logon via the current user's Run registry key.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TASK_NAME = "FingerprintLauncher"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "FingerprintLauncher"


def setup_user_autostart(exe_path: str | None = None, *, start_in_tray: bool = False) -> None:
    """Register the GUI to start at user logon.

    HKCU Run entries are visible in Task Manager's Startup tab and run inside
    the current interactive user session, which is what the GUI and WinBio
    monitoring need.
    """

    if sys.platform != "win32":
        return
    import winreg

    _delete_legacy_scheduled_task()
    command = _gui_launch_command(exe_path, start_in_tray=True) if start_in_tray else _gui_launch_command(exe_path)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)


def remove_user_autostart() -> None:
    if sys.platform != "win32":
        return
    _delete_legacy_scheduled_task()
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_VALUE)
    except FileNotFoundError:
        pass


def bootstrap_distribution(*, start_in_tray: bool = False) -> list[str]:
    """Best-effort autostart registration. Failures are non-fatal."""

    errors: list[str] = []
    if sys.platform != "win32":
        return errors
    try:
        setup_user_autostart(start_in_tray=start_in_tray)
    except Exception as exc:
        errors.append(f"Autostart setup failed: {exc}")
    return errors


def _gui_launch_command(exe_path: str | None = None, *, start_in_tray: bool = False) -> str:
    args = ["--tray"] if start_in_tray else []
    if _is_frozen():
        executable = exe_path or sys.executable
        return subprocess.list2cmdline([str(executable), *args])
    script = str(Path(__file__).resolve().parents[1] / "main.py")
    return subprocess.list2cmdline([str(sys.executable), script, *args])


def _quote(value: str) -> str:
    return subprocess.list2cmdline([str(value)])


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) or globals().get("__compiled__"))


def _creation_no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _delete_legacy_scheduled_task() -> None:
    subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", TASK_NAME, "/F"],
        check=False,
        creationflags=_creation_no_window(),
    )
