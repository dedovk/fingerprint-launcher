"""One-shot fingerprint scan launched by the configured hotkey."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.database import Database
from core.executor import execute_command
from core.winbio import (
    S_OK,
    TRANSIENT_IDENTIFY_HRESULTS,
    WINBIO_E_NO_MATCH,
    WINBIO_E_UNKNOWN_ID,
    WINBIO_POOL_PRIVATE,
    WINBIO_POOL_SYSTEM,
    WinBioSession,
    acquire_focus,
    enumerate_biometric_units,
    format_hresult,
    hresult_message,
    identity_key,
    release_focus,
)
from ui.i18n import tr


_IDENTIFY_TIMEOUT_MS = 15000


class TriggeredFingerprintScan(QObject):
    activity = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, db_path: str | Path, lang: str = "uk") -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.lang = lang
        self._session: WinBioSession | None = None
        self._cancelled = False

    @pyqtSlot()
    def run(self) -> None:
        db = Database(self.db_path)
        try:
            try:
                acquire_focus()
            except Exception as exc:
                logger.warning(
                    f"WinBioAcquireFocus failed for triggered scan: {exc}")

            session = self._open_session()
            if session is None:
                self.error.emit(tr(self.lang, "sensor_unavailable"))
                return

            result = session.identify(timeout_ms=_IDENTIFY_TIMEOUT_MS)
            if self._cancelled:
                return
            if result is None:
                self.error.emit(tr(self.lang, "timeout"))
                return

            self._handle_result(db, result)
        except Exception as exc:
            logger.exception(f"Triggered fingerprint scan failed: {exc}")
            self.error.emit(str(exc))
        finally:
            release_focus()
            self._close_session()
            db.close()
            self.finished.emit()

    def _open_session(self) -> WinBioSession | None:
        try:
            units = enumerate_biometric_units()
        except Exception as exc:
            logger.exception(f"Unable to enumerate biometric units: {exc}")
            return None

        has_private = any(unit.pool_type ==
                          WINBIO_POOL_PRIVATE for unit in units)
        pools = [WINBIO_POOL_PRIVATE] if has_private else []
        pools.append(WINBIO_POOL_SYSTEM)

        for pool in pools:
            try:
                self._session = WinBioSession(pool)
                return self._session
            except Exception as exc:
                logger.warning(
                    f"Unable to open WinBio session on pool {pool}: {exc}")
        return None

    def _handle_result(self, db: Database, result) -> None:
        if result.hr == S_OK:
            self._dispatch_match(db, result)
            return

        if result.hr == WINBIO_E_UNKNOWN_ID:
            self.error.emit(tr(self.lang, "unknown_hello").replace("\n", " "))
            return

        if result.hr == WINBIO_E_NO_MATCH:
            self.error.emit(tr(self.lang, "no_match"))
            return

        if result.hr in TRANSIENT_IDENTIFY_HRESULTS:
            self.error.emit(hresult_message(result.hr))
            return

        self.error.emit(
            f"{format_hresult(result.hr)}: {hresult_message(result.hr)}")

    def _dispatch_match(self, db: Database, result) -> None:
        guid = result.guid or ""
        identity_value = result.identity_value or guid
        sub_factor = int(result.sub_factor)

        if guid:
            db.update_guid(sub_factor, guid)
        elif identity_value:
            db.update_identity(
                sub_factor, result.identity_type, identity_value)

        commands = db.get_commands(
            guid, sub_factor, result.identity_type, identity_value)
        key = identity_key(result.identity_type, identity_value, sub_factor)
        if not commands:
            self.error.emit(
                f"{tr(self.lang, 'no_action')}: {result.finger_name} ({key})")
            return

        for command in commands:
            execute_command(command)

        details = self._format_action_details(commands)
        self.activity.emit(f"{result.finger_name}: {details}")

    def _format_action_details(self, commands: list) -> str:
        details = []
        for command in commands:
            data = command.get("command_data", {})
            detail = (data.get("path") or data.get("url") or data.get("keys") or
                      data.get("cmd") or ("LockWorkStation" if command["command_type"] == "lock_screen" else ""))
            if detail:
                details.append(detail)
        return ", ".join(details) if details else tr(self.lang, "executed")

    def _close_session(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                logger.exception("Error while closing triggered scan session")
            self._session = None

    @pyqtSlot()
    def cancel(self) -> None:
        self._cancelled = True
        if self._session is not None:
            try:
                self._session.cancel()
            except Exception:
                pass
