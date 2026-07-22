"""One-shot fingerprint scan launched by the configured hotkey."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from loguru import logger
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.action_registry import format_action_summary
from core.action_runner import ActionResult, ActionRunner, ActionStatus, ErrorPolicy
from core.database import Database
from core.winbio import (
    E_ACCESSDENIED,
    S_OK,
    TRANSIENT_IDENTIFY_HRESULTS,
    WINBIO_E_NO_MATCH,
    WINBIO_E_UNKNOWN_ID,
    WINBIO_POOL_PRIVATE,
    WINBIO_POOL_SYSTEM,
    WinBioSession,
    WinBioError,
    acquire_focus,
    enumerate_biometric_units,
    format_hresult,
    identity_key,
    release_focus,
)
from ui.i18n import action_labels, localized_finger_name, localized_winbio_message, tr


_IDENTIFY_TIMEOUT_MS = 15000


class TriggeredFingerprintScan(QObject):
    activity = pyqtSignal(str)
    matched = pyqtSignal(str)
    action_result = pyqtSignal(dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        db_path: str | Path,
        lang: str = "uk",
        timer_scheduler: Callable[[dict], None] | None = None,
    ) -> None:
        super().__init__()
        self.db_path = Path(db_path)
        self.lang = lang
        self.timer_scheduler = timer_scheduler
        self._session: WinBioSession | None = None
        self._runner: ActionRunner | None = None
        self._cancelled = False

    @pyqtSlot()
    def run(self) -> None:
        db = Database(self.db_path)
        try:
            try:
                acquire_focus()
            except WinBioError as exc:
                if exc.hr == E_ACCESSDENIED:
                    logger.trace(
                        f"WinBioAcquireFocus denied for triggered scan: {exc}")
                else:
                    logger.warning(
                        f"WinBioAcquireFocus failed for triggered scan: {exc}")
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
        except WinBioError as exc:
            logger.exception(f"Triggered fingerprint scan failed: {exc}")
            self.error.emit(
                f"{format_hresult(exc.hr)}: {localized_winbio_message(self.lang, exc.hr)}"
            )
        except Exception as exc:
            logger.exception(f"Triggered fingerprint scan failed: {exc}")
            self.error.emit(tr(self.lang, "scan_failed").format(error=exc))
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
            self.error.emit(localized_winbio_message(self.lang, result.hr))
            return

        self.error.emit(
            f"{format_hresult(result.hr)}: {localized_winbio_message(self.lang, result.hr)}")

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
        finger_name = localized_finger_name(self.lang, sub_factor)
        if not commands:
            self.error.emit(
                f"{tr(self.lang, 'no_action')}: {finger_name} ({key})")
            return

        self.matched.emit(finger_name)

        self._runner = ActionRunner(
            error_policy=ErrorPolicy.CONTINUE,
            on_result=self._emit_action_result,
            timer_scheduler=self.timer_scheduler,
        )
        report = self._runner.run(commands)
        self._runner = None

        if report.status == ActionStatus.CANCELLED:
            return
        failed = [result for result in report.results if result.status == ActionStatus.FAILED]
        if failed:
            labels = action_labels(self.lang)
            for failed_result in failed:
                logger.warning(
                    "Fingerprint action failed: type={} error={}",
                    failed_result.command_type,
                    failed_result.error or failed_result.message,
                )
            self.error.emit("; ".join(
                f"{tr(self.lang, 'action_result_failed')}: "
                f"{labels.get(result.command_type, result.command_type)}"
                for result in failed
            ))
            return

        details = self._format_action_details(commands)
        self.activity.emit(f"{finger_name}: {details}")

    def _emit_action_result(self, result: ActionResult) -> None:
        self.action_result.emit(result.to_dict())

    def _format_action_details(self, commands: list) -> str:
        details = []
        labels = action_labels(self.lang)
        for command in commands:
            detail = format_action_summary(
                command["command_type"],
                command.get("command_data"),
                labels.get(command["command_type"], command["command_type"]),
            )
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
        if self._runner is not None:
            self._runner.cancel()
        if self._session is not None:
            try:
                self._session.cancel()
            except Exception:
                pass
