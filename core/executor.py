"""Command execution backends for recognized fingers."""

from __future__ import annotations

import ctypes
import os
import shlex
import subprocess
import sys
import webbrowser
from typing import Any


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


def execute_command(command: dict[str, Any]) -> None:
    command_type = command.get("command_type")
    data = command.get("command_data") or {}

    if command_type == "launch_app":
        _launch_app(data)
    elif command_type == "open_url":
        _open_url(data)
    elif command_type == "hotkey":
        _hotkey(data)
    elif command_type == "shell":
        _shell(data)
    elif command_type == "lock_screen":
        _lock_screen()
    else:
        raise CommandExecutionError(f"Unknown command type: {command_type}")


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
