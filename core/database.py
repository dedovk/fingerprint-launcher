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
                updated_at TEXT DEFAULT (datetime('now'))
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
        if self._has_unique_sub_factor_constraint():
            self._rebuild_fingers_without_unique_sub_factor()

    def _has_unique_sub_factor_constraint(self) -> bool:
        indexes = self._conn.execute("PRAGMA index_list(fingers)").fetchall()
        for index in indexes:
            if not index["unique"]:
                continue
            columns = self._conn.execute(
                f"PRAGMA index_info({index['name']})"
            ).fetchall()
            if [column["name"] for column in columns] == ["sub_factor"]:
                return True
        return False

    def _rebuild_fingers_without_unique_sub_factor(self) -> None:
        self._conn.commit()
        self._conn.execute("PRAGMA foreign_keys = OFF")
        try:
            self._conn.executescript(
                """
                CREATE TABLE fingers_new (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    guid       TEXT NOT NULL,
                    identity_type INTEGER DEFAULT 2,
                    identity_value TEXT,
                    sub_factor INTEGER NOT NULL,
                    label      TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                INSERT INTO fingers_new (
                    id, guid, identity_type, identity_value, sub_factor,
                    label, created_at, updated_at
                )
                SELECT
                    id, guid, identity_type, identity_value, sub_factor,
                    label, created_at, updated_at
                FROM fingers;

                DROP TABLE fingers;
                ALTER TABLE fingers_new RENAME TO fingers;
                """
            )
            self._conn.commit()
        finally:
            self._conn.execute("PRAGMA foreign_keys = ON")

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
        finger_id: int | None = None,
    ) -> int:
        stored_identity = identity_value or guid
        if finger_id is not None:
            self._conn.execute(
                """
                UPDATE fingers
                SET guid = ?, identity_type = ?, identity_value = ?,
                    sub_factor = ?, label = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (guid, identity_type, stored_identity, sub_factor, label, finger_id),
            )
            self._conn.commit()
            return int(finger_id)

        cur = self._conn.execute(
            """
            INSERT INTO fingers (guid, identity_type, identity_value, sub_factor, label)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guid, identity_type, stored_identity, sub_factor, label),
        )
        self._conn.commit()
        return int(cur.lastrowid)

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

    def replace_commands(self, finger_id: int, commands: list[dict[str, Any]]) -> None:
        """Replace all commands for a finger with the provided command list."""
        normalized_commands = [
            command
            for command in (self._normalize_command(command) for command in commands)
            if command is not None
        ]

        with self._conn:
            self._conn.execute("DELETE FROM commands WHERE finger_id = ?", (finger_id,))
            self._conn.executemany(
                """
                INSERT INTO commands (finger_id, command_type, command_data, enabled)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        finger_id,
                        command["command_type"],
                        json.dumps(command["command_data"]),
                        int(command.get("enabled", True)),
                    )
                    for command in normalized_commands
                ],
            )

    def get_commands_by_finger_id(self, finger_id: int) -> list[dict[str, Any]]:
        """Return all commands attached to one finger row, including disabled ones."""
        rows = self._conn.execute(
            """
            SELECT id, finger_id, command_type, command_data, enabled
            FROM commands
            WHERE finger_id = ?
            ORDER BY id ASC
            """,
            (finger_id,),
        ).fetchall()

        result = []
        for row in rows:
            data = dict(row)
            data["command_data"] = json.loads(data["command_data"])
            result.append(data)
        return result

    def _normalize_command(self, command: dict[str, Any]) -> dict[str, Any] | None:
        command_type = command.get("command_type") or command.get("type")
        if not command_type:
            return None

        command_data = command.get("command_data")
        if command_data is None:
            command_data = command.get("data")
        if command_data is None:
            command_data = {}
        elif isinstance(command_data, str):
            try:
                command_data = json.loads(command_data)
            except json.JSONDecodeError:
                command_data = {}
        elif not isinstance(command_data, dict):
            command_data = {}

        return {
            "command_type": str(command_type),
            "command_data": command_data,
            "enabled": bool(command.get("enabled", True)),
        }

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
