import sqlite3

from core.database import Database
from core.winbio import WINBIO_ID_TYPE_SID


def test_save_finger_allows_multiple_profiles_for_same_sub_factor(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        first_id = db.save_finger("guid-1", 0x03, "finger")
        second_id = db.save_finger("guid-1", 0x03, "finger profile 2")

        assert first_id != second_id
        fingers = db.list_fingers()
        assert len(fingers) == 2
        assert [finger["label"] for finger in fingers] == ["finger", "finger profile 2"]


def test_save_finger_updates_existing_profile_by_id(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        finger_id = db.save_finger("guid-1", 0x03, "finger")

        updated_id = db.save_finger(
            "guid-2",
            0x04,
            "updated finger",
            finger_id=finger_id,
        )

        assert updated_id == finger_id
        fingers = db.list_fingers()
        assert len(fingers) == 1
        assert fingers[0]["guid"] == "guid-2"
        assert fingers[0]["sub_factor"] == 0x04
        assert fingers[0]["label"] == "updated finger"


def test_database_migration_removes_old_sub_factor_unique_constraint(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE fingers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT NOT NULL,
            identity_type INTEGER DEFAULT 2,
            identity_value TEXT,
            sub_factor INTEGER NOT NULL,
            label TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(sub_factor)
        );
        CREATE TABLE commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finger_id INTEGER NOT NULL REFERENCES fingers(id) ON DELETE CASCADE,
            command_type TEXT NOT NULL,
            command_data TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO fingers (guid, identity_value, sub_factor, label)
        VALUES ('old-guid', 'old-guid', 3, 'old finger');
        INSERT INTO commands (finger_id, command_type, command_data)
        VALUES (1, 'open_url', '{"url": "https://github.com"}');
        """
    )
    conn.close()

    with Database(db_path) as db:
        first_id = db.save_finger("guid-1", 0x03, "finger")
        second_id = db.save_finger("guid-1", 0x03, "finger profile 2")

        assert first_id != second_id
        commands = db.get_commands_by_finger_id(1)
        assert len(commands) == 1
        assert commands[0]["command_data"]["url"] == "https://github.com"


def test_update_guid_silently_updates_existing_sub_factor(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        finger_id = db.save_finger("old-guid", 0x08, "finger")
        db.save_command(finger_id, "open_url", {"url": "https://github.com"})

        db.update_guid(0x08, "new-guid")

        command = db.get_command("new-guid", 0x08)
        assert command is not None
        assert command["command_type"] == "open_url"
        assert command["command_data"]["url"] == "https://github.com"


def test_sid_identity_can_be_used_as_command_key(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        sid = "S-1-5-21-3661863302-2766317350-1867922774-1001"
        finger_id = db.save_finger(
            "",
            0xF5,
            "finger",
            identity_type=WINBIO_ID_TYPE_SID,
            identity_value=sid,
        )
        db.save_command(finger_id, "lock_screen", {})

        command = db.get_command("", 0xF5, WINBIO_ID_TYPE_SID, sid)

        assert command is not None
        assert command["identity_type"] == WINBIO_ID_TYPE_SID
        assert command["identity_value"] == sid
        assert command["command_type"] == "lock_screen"


def test_command_enabled_can_be_toggled(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        finger_id = db.save_finger("guid-1", 0x03, "finger")
        command_id = db.save_command(finger_id, "open_url", {"url": "https://github.com"})

        assert db.get_command("guid-1", 0x03) is not None
        db.set_command_enabled(command_id, False)
        assert db.get_command("guid-1", 0x03) is None
        db.set_command_enabled(command_id, True)
        assert db.get_command("guid-1", 0x03) is not None


def test_replace_commands_removes_deleted_actions(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        finger_id = db.save_finger("guid-1", 0x03, "finger")
        db.save_command(finger_id, "open_url", {"url": "https://github.com"})
        db.save_command(finger_id, "launch_app", {"path": "Code.exe", "args": ""})

        db.replace_commands(
            finger_id,
            [
                {
                    "command_type": "launch_app",
                    "command_data": {"path": "Code.exe", "args": ""},
                }
            ],
        )

        commands = db.get_commands("guid-1", 0x03)
        assert len(commands) == 1
        assert commands[0]["command_type"] == "launch_app"
        assert commands[0]["command_data"]["path"] == "Code.exe"


def test_replace_commands_accepts_type_alias_and_bad_data(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        finger_id = db.save_finger("guid-1", 0x03, "finger")

        db.replace_commands(
            finger_id,
            [
                {"type": "open_url", "command_data": {"url": "https://github.com"}},
                {"command_type": "lock_screen", "command_data": ["not", "a", "dict"]},
                {"command_data": {"url": "missing-type"}},
            ],
        )

        commands = db.get_commands("guid-1", 0x03)
        assert len(commands) == 2
        assert commands[0]["command_type"] == "open_url"
        assert commands[0]["command_data"]["url"] == "https://github.com"
        assert commands[1]["command_type"] == "lock_screen"
        assert commands[1]["command_data"] == {}


def test_get_commands_by_finger_id_returns_all_attached_commands(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        finger_id = db.save_finger("guid-1", 0x03, "finger")
        db.save_command(finger_id, "open_url", {"url": "https://github.com"})
        db.save_command(finger_id, "launch_app", {"path": "Code.exe", "args": ""})

        commands = db.get_commands_by_finger_id(finger_id)

        assert [command["command_type"] for command in commands] == ["open_url", "launch_app"]
        assert commands[0]["command_data"]["url"] == "https://github.com"
        assert commands[1]["command_data"]["path"] == "Code.exe"


def test_settings_roundtrip(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        assert db.get_setting("missing", "fallback") == "fallback"
        db.set_setting("autostart", "1")
        assert db.get_setting("autostart") == "1"
