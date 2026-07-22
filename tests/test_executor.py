from unittest.mock import call, patch

import pytest

from core.executor import CommandExecutionError, execute_command
from core.execution import ExecutionContext


def test_open_url_uses_windows_default_browser():
    with patch("core.executor.sys.platform", "win32"), \
            patch("core.executor.os.startfile", create=True) as open_url:
        execute_command({"command_type": "open_url", "command_data": {"url": "https://github.com"}})
    open_url.assert_called_once_with("https://github.com")


def test_open_url_normalizes_domains_and_plain_text_for_default_browser():
    with patch("core.executor.sys.platform", "win32"), \
            patch("core.executor.os.startfile", create=True) as open_url:
        execute_command({"command_type": "open_url", "command_data": {"url": "example.com"}})
        execute_command({"command_type": "open_url", "command_data": {"url": "ordinary text"}})

    assert open_url.call_args_list == [
        call("https://example.com"),
        call("https://www.google.com/search?q=ordinary+text"),
    ]


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


def test_restart_uses_windows_restart(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("subprocess.Popen") as popen:
        execute_command({"command_type": "restart", "command_data": {}})

    popen.assert_called_once()
    assert popen.call_args.args[0] == ["shutdown.exe", "/r", "/t", "0"]
    assert "creationflags" in popen.call_args.kwargs


def test_minimize_all_uses_winapi_without_synthetic_hotkey(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("core.executor.ctypes.windll.user32") as user32, \
            patch("keyboard.send") as send:
        user32.GetShellWindow.return_value = 999
        user32.IsWindowVisible.return_value = 1
        user32.GetWindow.return_value = 0
        user32.GetWindowTextLengthW.return_value = 8

        def enumerate_windows(callback, _lparam):
            assert callback(101, 0)
            assert callback(202, 0)
            return 1

        user32.EnumWindows.side_effect = enumerate_windows
        execute_command({"command_type": "minimize_all", "command_data": {}})

    send.assert_not_called()
    assert user32.ShowWindow.call_args_list == [
        ((101, 6),),
        ((202, 6),),
    ]


def test_toggle_mute_uses_windows_audio(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("core.executor.windows_audio.toggle_mute") as toggle_mute:
        execute_command({"command_type": "toggle_mute", "command_data": {}})

    toggle_mute.assert_called_once_with()


@pytest.mark.parametrize(
    ("direction", "amount", "expected_delta"),
    [("increase", 15, 15), ("decrease", 25, -25)],
)
def test_change_volume_uses_signed_relative_delta(
    monkeypatch, direction, amount, expected_delta
):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("core.executor.windows_audio.change_volume") as change_volume:
        execute_command({
            "command_type": "change_volume",
            "command_data": {"direction": direction, "amount_percent": amount},
        })

    change_volume.assert_called_once_with(expected_delta)


def test_close_active_window_targets_window_captured_before_scan(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    context = ExecutionContext()
    context.command_metadata = {"target_window_handle": 1234}
    with patch("core.executor.ctypes.windll.user32") as user32:
        user32.IsWindow.return_value = 1
        user32.PostMessageW.return_value = 1
        execute_command(
            {"command_type": "close_active_window", "command_data": {}},
            context=context,
        )

    user32.GetForegroundWindow.assert_not_called()
    user32.IsWindow.assert_called_once_with(1234)
    user32.PostMessageW.assert_called_once_with(1234, 0x0010, 0, 0)


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


def test_delay_uses_cancellable_execution_context_sleep():
    context = ExecutionContext()
    with patch.object(context, "sleep") as sleep:
        execute_command(
            {"command_type": "delay", "command_data": {"duration_ms": 1_500}},
            context=context,
        )

    sleep.assert_called_once_with(1.5)


def test_quick_timer_schedules_without_sleeping():
    scheduled = []
    context = ExecutionContext(timer_scheduler=scheduled.append)
    context.command_metadata = {"command_id": 7, "finger_label": "Index"}

    execute_command(
        {
            "command_type": "quick_timer",
            "command_data": {
                "duration_ms": 120_000,
                "message": "Tea",
                "sound_path": "",
            },
        },
        context=context,
    )

    assert scheduled == [{
        "schema_version": 1,
        "duration_ms": 120_000,
        "message": "Tea",
        "sound_path": "",
        "command_id": 7,
        "finger_label": "Index",
    }]
