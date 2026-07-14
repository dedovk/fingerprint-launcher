from unittest.mock import patch

import pytest

from core.executor import CommandExecutionError, execute_command


def test_open_url_uses_webbrowser():
    with patch("webbrowser.open") as open_url:
        execute_command({"command_type": "open_url", "command_data": {"url": "https://github.com"}})
    open_url.assert_called_once_with("https://github.com")


def test_launch_app_uses_argument_list():
    with patch("subprocess.Popen") as popen:
        execute_command({"command_type": "launch_app", "command_data": {"path": "Code.exe", "args": "--new-window"}})
    popen.assert_called_once()
    assert popen.call_args.args[0] == ["Code.exe", "--new-window"]


def test_unknown_command_type_raises():
    with pytest.raises(CommandExecutionError):
        execute_command({"command_type": "nope", "command_data": {}})


def test_shell_uses_powershell_on_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("subprocess.Popen") as popen:
        execute_command({"command_type": "shell", "command_data": {"cmd": "Write-Output test"}})

    popen.assert_called_once()
    assert popen.call_args.args[0] == [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        "Write-Output test",
    ]
    assert "creationflags" in popen.call_args.kwargs


def test_shutdown_uses_windows_shutdown(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("subprocess.Popen") as popen:
        execute_command({"command_type": "shutdown", "command_data": {}})

    popen.assert_called_once()
    assert popen.call_args.args[0] == ["shutdown.exe", "/s", "/t", "0"]
    assert "creationflags" in popen.call_args.kwargs


def test_sleep_uses_windows_suspend_command(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("subprocess.Popen") as popen:
        execute_command({"command_type": "sleep", "command_data": {}})

    popen.assert_called_once()
    assert popen.call_args.args[0] == [
        "rundll32.exe",
        "powrprof.dll,SetSuspendState",
        "0,1,0",
    ]
    assert "creationflags" in popen.call_args.kwargs


def test_paste_text_only_copies_text_to_clipboard(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("core.executor._set_windows_clipboard_text") as set_clipboard, \
            patch("keyboard.send") as send:
        execute_command({"command_type": "paste_text", "command_data": {"text": "hello"}})

    set_clipboard.assert_called_once_with("hello")
    send.assert_not_called()


def test_paste_text_requires_text(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with pytest.raises(CommandExecutionError):
        execute_command({"command_type": "paste_text", "command_data": {"text": ""}})
