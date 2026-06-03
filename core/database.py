"""SQLite persistence for finger bindings, commands, and settings."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from core.winbio import WINBIO_ID_TYPE_GUID


DEFAULT_DB_PATH = Path.home() / "AppData" / "Local" / \
    "FingerprintLauncher" / "fingerprints.sqlite3"


class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fingers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                guid       TEXT NOT NULL,
                identity_type INTEGER DEFAULT 2,
                identity_value TEXT,
                sub_factor INTEGER NOT NULL,
                label      TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(sub_factor)
            );

            CREATE TABLE IF NOT EXISTS commands (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                finger_id    INTEGER NOT NULL REFERENCES fingers(id) ON DELETE CASCADE,
                command_type TEXT NOT NULL,
                command_data TEXT NOT NULL,
                enabled      INTEGER DEFAULT 1,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._migrate_schema()
        self._conn.commit()

    def _migrate_schema(self) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(fingers)").fetchall()
        }
        if "identity_type" not in columns:
            self._conn.execute(
                "ALTER TABLE fingers ADD COLUMN identity_type INTEGER DEFAULT 2")
        if "identity_value" not in columns:
            self._conn.execute(
                "ALTER TABLE fingers ADD COLUMN identity_value TEXT")
        self._conn.execute(
            "UPDATE fingers SET identity_value=guid WHERE identity_value IS NULL OR identity_value=''"
        )

    def get_command(
        self,
        guid: str,
        sub_factor: int,
        identity_type: int | None = None,
        identity_value: str | None = None,
    ) -> dict[str, Any] | None:
        lookup_value = identity_value or guid
        if identity_type is None:
            where = "(f.identity_value = ? OR f.guid = ?) AND f.sub_factor = ? AND c.enabled = 1"
            params = (lookup_value, lookup_value, sub_factor)
        else:
            where = "f.identity_type = ? AND f.identity_value = ? AND f.sub_factor = ? AND c.enabled = 1"
            params = (identity_type, lookup_value, sub_factor)

        row = self._conn.execute(
            f"""
            SELECT c.id, c.finger_id, c.command_type, c.command_data, c.enabled,
                   f.guid, f.identity_type, f.identity_value, f.sub_factor, f.label
            FROM fingers f
            JOIN commands c ON c.finger_id = f.id
            WHERE {where}
            ORDER BY c.id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        if row is None:
            return None

        data = dict(row)
        data["command_data"] = json.loads(data["command_data"])
        return data

    def get_commands(
        self,
        guid: str,
        sub_factor: int,
        identity_type: int | None = None,
        identity_value: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all enabled commands for a finger. Allows executing multiple actions.
        """
        lookup_value = identity_value or guid
        if identity_type is None:
            where = "(f.identity_value = ? OR f.guid = ?) AND f.sub_factor = ? AND c.enabled = 1"
            params = (lookup_value, lookup_value, sub_factor)
        else:
            where = "f.identity_type = ? AND f.identity_value = ? AND f.sub_factor = ? AND c.enabled = 1"
            params = (identity_type, lookup_value, sub_factor)

        rows = self._conn.execute(
            f"""
            SELECT c.id, c.finger_id, c.command_type, c.command_data, c.enabled,
                   f.guid, f.identity_type, f.identity_value, f.sub_factor, f.label
            FROM fingers f
            JOIN commands c ON c.finger_id = f.id
            WHERE {where}
            ORDER BY c.id ASC
            """,
            params,
        ).fetchall()

        result = []
        for row in rows:
            data = dict(row)
            data["command_data"] = json.loads(data["command_data"])
            result.append(data)
        return result

    def save_finger(
        self,
        guid: str,
        sub_factor: int,
        label: str,
        identity_type: int = WINBIO_ID_TYPE_GUID,
        identity_value: str | None = None,
    ) -> int:
        stored_identity = identity_value or guid
        self._conn.execute(
            """
            INSERT INTO fingers (guid, identity_type, identity_value, sub_factor, label)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sub_factor) DO UPDATE SET
                guid = excluded.guid,
                identity_type = excluded.identity_type,
                identity_value = excluded.identity_value,
                label = excluded.label,
                updated_at = datetime('now')
            """,
            (guid, identity_type, stored_identity, sub_factor, label),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT id FROM fingers WHERE sub_factor = ?",
            (sub_factor,),
        ).fetchone()
        return int(row["id"])

    def save_command(
        self,
        finger_id: int,
        command_type: str,
        command_data: dict[str, Any],
        enabled: bool = True,
    ) -> int:
        """
        Save a new command for a finger. Allows multiple commands per finger.
        """
        cur = self._conn.execute(
            """
            INSERT INTO commands (finger_id, command_type, command_data, enabled)
            VALUES (?, ?, ?, ?)
            """,
            (finger_id, command_type, json.dumps(command_data), int(enabled)),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def set_command_enabled(self, command_id: int, enabled: bool) -> None:
        self._conn.execute(
            "UPDATE commands SET enabled = ? WHERE id = ?",
            (int(enabled), command_id),
        )
        self._conn.commit()

    def update_guid(self, sub_factor: int, new_guid: str) -> None:
        """
        Викликати КОЖНОГО РАЗУ при успішному identify().
        Якщо юзер перереєстрував відбиток в Windows Hello —
        GUID зміниться, але sub_factor залишиться тим самим.
        Тихо оновлюємо GUID без участі юзера.
        """

        self._conn.execute(
            "UPDATE fingers SET guid=?, identity_type=?, identity_value=?, updated_at=datetime('now') "
            "WHERE sub_factor=? AND guid!=?",
            (new_guid, WINBIO_ID_TYPE_GUID, new_guid, sub_factor, new_guid),
        )
        self._conn.commit()

    def update_identity(self, sub_factor: int, identity_type: int, identity_value: str) -> None:
        self._conn.execute(
            """
            UPDATE fingers
            SET identity_type=?, identity_value=?, updated_at=datetime('now')
            WHERE sub_factor=? AND (identity_type!=? OR identity_value!=?)
            """,
            (identity_type, identity_value, sub_factor,
             identity_type, identity_value),
        )
        self._conn.commit()

    def delete_finger(self, finger_id: int) -> None:
        self._conn.execute("DELETE FROM fingers WHERE id = ?", (finger_id,))
        self._conn.commit()

    def list_fingers(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT f.id, f.guid, f.identity_type, f.identity_value, f.sub_factor,
                   f.label, f.created_at, f.updated_at,
                   c.id AS command_id, c.command_type, c.command_data, c.enabled
            FROM fingers f
            LEFT JOIN commands c ON c.finger_id = f.id
            ORDER BY f.sub_factor
            """
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get("command_data"):
                item["command_data"] = json.loads(item["command_data"])
            result.append(item)
        return result

    def get_setting(self, key: str, default=None) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return default if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
