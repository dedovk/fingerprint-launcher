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

