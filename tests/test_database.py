from core.database import Database
from core.winbio import WINBIO_ID_TYPE_SID


def test_save_finger_upserts_by_sub_factor(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        first_id = db.save_finger("guid-1", 0x03, "finger")
        second_id = db.save_finger("guid-2", 0x03, "finger")

        assert first_id == second_id
        fingers = db.list_fingers()
        assert len(fingers) == 1
        assert fingers[0]["guid"] == "guid-2"


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


def test_settings_roundtrip(tmp_path):
    with Database(tmp_path / "test.sqlite3") as db:
        assert db.get_setting("missing", "fallback") == "fallback"
        db.set_setting("autostart", "1")
        assert db.get_setting("autostart") == "1"
