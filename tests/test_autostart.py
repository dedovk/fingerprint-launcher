import sys
from types import SimpleNamespace

from services import autostart


def test_missing_autostart_setting_migrates_to_disabled(tmp_path, monkeypatch):
    import main as app_main
    from core.database import Database

    removed = []
    monkeypatch.setattr(app_main, "remove_user_autostart", lambda: removed.append(True))
    monkeypatch.setattr(
        app_main,
        "bootstrap_distribution",
        lambda **_kwargs: ["unexpected"],
    )

    with Database(tmp_path / "autostart-default.sqlite3") as db:
        assert app_main.configure_autostart(db) == []
        assert db.get_setting("autostart") == "0"
        assert db.get_setting("autostart_mode") == "disabled"

    assert removed == [True]


def test_explicit_autostart_setting_is_preserved(tmp_path, monkeypatch):
    import main as app_main
    from core.database import Database

    calls = []
    monkeypatch.setattr(
        app_main,
        "bootstrap_distribution",
        lambda **kwargs: calls.append(kwargs) or ["setup result"],
    )
    monkeypatch.setattr(
        app_main,
        "remove_user_autostart",
        lambda: (_ for _ in ()).throw(AssertionError("must not remove explicit autostart")),
    )

    with Database(tmp_path / "autostart-enabled.sqlite3") as db:
        db.set_setting("autostart", "1")
        assert app_main.configure_autostart(db) == ["setup result"]
        assert db.get_setting("autostart") == "1"

    assert calls == [{"start_in_tray": False}]


def test_tray_autostart_mode_is_preserved_during_bootstrap(tmp_path, monkeypatch):
    import main as app_main
    from core.database import Database

    calls = []
    monkeypatch.setattr(
        app_main,
        "bootstrap_distribution",
        lambda **kwargs: calls.append(kwargs) or [],
    )

    with Database(tmp_path / "autostart-tray.sqlite3") as db:
        db.set_setting("autostart", "1")
        db.set_setting("autostart_mode", "current_user_tray")

        assert app_main.configure_autostart(db) == []

    assert calls == [{"start_in_tray": True}]


def test_setup_user_autostart_creates_run_value_and_removes_legacy_task(monkeypatch):
    calls = []
    registry_values = {}

    monkeypatch.setattr(autostart.sys, "platform", "win32")
    monkeypatch.setattr(autostart, "_gui_launch_command", lambda exe_path=None: '"C:\\App\\FingerprintLauncher.exe"')
    monkeypatch.setattr(autostart, "_creation_no_window", lambda: 123)

    def fake_run(args, check=False, creationflags=0):
        calls.append((args, check, creationflags))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(autostart.subprocess, "run", fake_run)

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    class FakeWinReg:
        HKEY_CURRENT_USER = object()
        REG_SZ = object()

        @staticmethod
        def CreateKey(root, path):
            registry_values["create"] = (root, path)
            return FakeKey()

        @staticmethod
        def SetValueEx(key, name, reserved, value_type, value):
            registry_values["set"] = (key, name, reserved, value_type, value)

    monkeypatch.setitem(sys.modules, "winreg", FakeWinReg)

    autostart.setup_user_autostart()

    assert calls == [
        (
            [
                "schtasks.exe",
                "/Delete",
                "/TN",
                autostart.TASK_NAME,
                "/F",
            ],
            False,
            123,
        )
    ]
    assert registry_values["create"] == (FakeWinReg.HKEY_CURRENT_USER, autostart.RUN_KEY)
    assert registry_values["set"] == (
        registry_values["set"][0],
        autostart.RUN_VALUE,
        0,
        FakeWinReg.REG_SZ,
        '"C:\\App\\FingerprintLauncher.exe"',
    )


def test_remove_user_autostart_deletes_task_and_ignores_missing_run_value(monkeypatch):
    calls = []

    monkeypatch.setattr(autostart.sys, "platform", "win32")
    monkeypatch.setattr(autostart, "_creation_no_window", lambda: 55)

    def fake_run(args, check=False, creationflags=0):
        calls.append((args, check, creationflags))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(autostart.subprocess, "run", fake_run)

    class FakeWinReg:
        HKEY_CURRENT_USER = object()
        KEY_SET_VALUE = object()

        @staticmethod
        def OpenKey(*_args, **_kwargs):
            raise FileNotFoundError

    monkeypatch.setitem(sys.modules, "winreg", FakeWinReg)

    autostart.remove_user_autostart()

    assert calls == [
        (
            ["schtasks.exe", "/Delete", "/TN", autostart.TASK_NAME, "/F"],
            False,
            55,
        )
    ]


def test_gui_launch_command_points_to_main_script_when_not_frozen(monkeypatch):
    monkeypatch.setattr(autostart, "_is_frozen", lambda: False)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\Python\python.exe")

    command = autostart._gui_launch_command()
    assert "main.py" in command
    assert "python.exe" in command


def test_gui_launch_command_uses_executable_in_frozen_build(monkeypatch):
    monkeypatch.setattr(autostart, "_is_frozen", lambda: True)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\App\FingerprintLauncher.exe")

    command = autostart._gui_launch_command()
    assert command == r"C:\App\FingerprintLauncher.exe"
    assert "main.py" not in command


def test_gui_launch_command_adds_tray_argument_to_frozen_build(monkeypatch):
    monkeypatch.setattr(autostart, "_is_frozen", lambda: True)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\App\FingerprintLauncher.exe")

    command = autostart._gui_launch_command(start_in_tray=True)

    assert command == r"C:\App\FingerprintLauncher.exe --tray"
