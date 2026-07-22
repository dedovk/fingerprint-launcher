"""Command execution backends for recognized fingers."""

from __future__ import annotations

import ctypes
import os
import shlex
import subprocess
import sys
import webbrowser
from typing import Any, Callable

from core.action_registry import ActionRegistryError, validate_command_data
from core.execution import ExecutionContext


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000 if os.name == "nt" else 0)


class CommandExecutionError(RuntimeError):
    pass


def _normalize_hotkey(keys: str) -> str:
    aliases = {
        "win": "windows",
        "meta": "windows",
        "cmd": "windows",
        "super": "windows",
        "lwin": "windows",
        "rwin": "windows",
    }
    tokens: list[str] = []
    for raw in keys.split("+"):
        token = raw.strip().lower()
        compact = token.replace(" ", "")
        if compact:
            tokens.append(aliases.get(compact, compact))
    return "+".join(tokens)


def execute_command(
    command: dict[str, Any],
    *,
    context: ExecutionContext | None = None,
) -> None:
    command_type = str(command.get("command_type") or "")
    try:
        data = validate_command_data(command_type, command.get("command_data"))
    except ActionRegistryError as exc:
        raise CommandExecutionError(str(exc)) from exc

    execution_context = context or ExecutionContext()
    execution_context.check_cancelled()
    try:
        handler = ACTION_HANDLERS[command_type]
    except KeyError as exc:
        raise CommandExecutionError(f"Unknown command type: {command_type}") from exc
    handler(data, execution_context)


def _launch_app(data: dict[str, Any]) -> None:
    path = str(data.get("path") or "").strip()
    if not path:
        raise CommandExecutionError("launch_app requires path")

    args = data.get("args") or ""
    if sys.platform == "win32" and not args:
        os.startfile(path)
        return

    argv = [path]
    if args:
        argv.extend(shlex.split(str(args), posix=False))
    subprocess.Popen(argv, close_fds=True)


def _open_url(data: dict[str, Any]) -> None:
    url = str(data.get("url") or "").strip()
    if not url:
        raise CommandExecutionError("open_url requires url")
    webbrowser.open(url)


def _hotkey(data: dict[str, Any]) -> None:
    keys = str(data.get("keys") or "").strip()
    if not keys:
        raise CommandExecutionError("hotkey requires keys")
    keys = _normalize_hotkey(keys)
    import keyboard

    keyboard.send(keys)


def _shell(data: dict[str, Any]) -> None:
    cmd = str(data.get("cmd") or "").strip()
    if not cmd:
        raise CommandExecutionError("shell requires cmd")

    hidden = bool(data.get("hidden", True))
    if sys.platform == "win32":
        flags = CREATE_NO_WINDOW if hidden else 0
        subprocess.Popen(["powershell.exe", "-NoProfile", "-Command", cmd], creationflags=flags)
        return

    # Non-Windows fallback for tests/dev only. No shell=True here either.
    subprocess.Popen(shlex.split(cmd))


def _lock_screen() -> None:
    if sys.platform != "win32":
        raise CommandExecutionError("lock_screen is only available on Windows")
    ctypes.windll.user32.LockWorkStation()


def _lock_screen_handler(_data: dict[str, Any]) -> None:
    _lock_screen()


def _shutdown() -> None:
    if sys.platform != "win32":
        raise CommandExecutionError("shutdown is only available on Windows")
    subprocess.Popen(["shutdown.exe", "/s", "/t", "0"], creationflags=CREATE_NO_WINDOW)


def _shutdown_handler(_data: dict[str, Any]) -> None:
    _shutdown()


def _restart() -> None:
    if sys.platform != "win32":
        raise CommandExecutionError("restart is only available on Windows")
    subprocess.Popen(["shutdown.exe", "/r", "/t", "0"], creationflags=CREATE_NO_WINDOW)


def _restart_handler(_data: dict[str, Any]) -> None:
    _restart()


def _minimize_all() -> None:
    if sys.platform != "win32":
        raise CommandExecutionError("minimize_all is only available on Windows")
    import keyboard

    keyboard.send("windows+m")


def _minimize_all_handler(_data: dict[str, Any]) -> None:
    _minimize_all()


def _sleep() -> None:
    if sys.platform != "win32":
        raise CommandExecutionError("sleep is only available on Windows")
    subprocess.Popen(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        creationflags=CREATE_NO_WINDOW,
    )


def _sleep_handler(_data: dict[str, Any]) -> None:
    _sleep()


def _copy_text_to_clipboard(data: dict[str, Any]) -> None:
    text = str(data.get("text") or "")
    if not text:
        raise CommandExecutionError("paste_text requires text")
    if sys.platform != "win32":
        raise CommandExecutionError("paste_text is only available on Windows")

    _set_windows_clipboard_text(text)


def _delay(data: dict[str, Any], context: ExecutionContext) -> None:
    context.sleep(int(data["duration_ms"]) / 1_000)


def _quick_timer(data: dict[str, Any], context: ExecutionContext) -> None:
    context.schedule_timer(data)


def _set_windows_clipboard_text(text: str) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int

    data = text.encode("utf-16-le") + b"\x00\x00"

    handle = kernel32.GlobalAlloc(0x0042, len(data))
    if not handle:
        raise CommandExecutionError("Unable to allocate clipboard memory")

    locked = kernel32.GlobalLock(handle)
    if not locked:
        kernel32.GlobalFree(handle)
        raise CommandExecutionError("Unable to lock clipboard memory")

    try:
        ctypes.memmove(locked, data, len(data))
    finally:
        kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        raise CommandExecutionError("Unable to open clipboard")

    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(13, handle):
            kernel32.GlobalFree(handle)
            raise CommandExecutionError("Unable to set clipboard text")
        handle = None
    finally:
        user32.CloseClipboard()


def _cancellable(handler: Callable[[dict[str, Any]], None]):
    def wrapped(data: dict[str, Any], context: ExecutionContext) -> None:
        context.check_cancelled()
        handler(data)

    return wrapped


ACTION_HANDLERS = {
    "launch_app": _cancellable(_launch_app),
    "open_url": _cancellable(_open_url),
    "hotkey": _cancellable(_hotkey),
    "shell": _cancellable(_shell),
    "lock_screen": _cancellable(_lock_screen_handler),
    "minimize_all": _cancellable(_minimize_all_handler),
    "shutdown": _cancellable(_shutdown_handler),
    "restart": _cancellable(_restart_handler),
    "sleep": _cancellable(_sleep_handler),
    "paste_text": _cancellable(_copy_text_to_clipboard),
    "delay": _delay,
    "quick_timer": _quick_timer,
}
