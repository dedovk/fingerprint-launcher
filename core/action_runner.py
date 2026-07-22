"""Sequential action runner with timing, cancellation, and structured results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from time import perf_counter
from typing import Any, Callable, Iterable

from core.action_registry import format_action_summary, validate_command_data
from core.execution import CancellationToken, CommandCancelledError, ExecutionContext, TimerScheduler
from core.executor import execute_command


class ActionStatus(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorPolicy(str, Enum):
    CONTINUE = "continue"
    STOP = "stop"


@dataclass(frozen=True)
class ActionResult:
    index: int
    command_type: str
    status: ActionStatus
    message: str
    duration_seconds: float
    command_data: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass(frozen=True)
class RunReport:
    results: tuple[ActionResult, ...]

    @property
    def status(self) -> ActionStatus:
        statuses = {result.status for result in self.results}
        if ActionStatus.FAILED in statuses:
            return ActionStatus.FAILED
        if ActionStatus.CANCELLED in statuses:
            return ActionStatus.CANCELLED
        if statuses and statuses == {ActionStatus.SKIPPED}:
            return ActionStatus.SKIPPED
        return ActionStatus.SUCCESS

    @property
    def successful(self) -> bool:
        return self.status == ActionStatus.SUCCESS


Executor = Callable[[dict[str, Any], ExecutionContext], None]
ResultCallback = Callable[[ActionResult], None]


def _default_executor(command: dict[str, Any], context: ExecutionContext) -> None:
    execute_command(command, context=context)


class ActionRunner:
    def __init__(
        self,
        *,
        error_policy: ErrorPolicy = ErrorPolicy.CONTINUE,
        token: CancellationToken | None = None,
        executor: Executor | None = None,
        on_result: ResultCallback | None = None,
        timer_scheduler: TimerScheduler | None = None,
    ) -> None:
        self.error_policy = error_policy
        self.token = token or CancellationToken()
        self.context = ExecutionContext(self.token, timer_scheduler=timer_scheduler)
        self.executor = executor or _default_executor
        self.on_result = on_result

    def cancel(self) -> None:
        self.token.cancel()

    def run(self, commands: Iterable[dict[str, Any]]) -> RunReport:
        results: list[ActionResult] = []
        for index, original_command in enumerate(commands):
            command = dict(original_command)
            command_type = str(command.get("command_type") or "")
            started = perf_counter()

            if self.token.is_cancelled:
                result = self._result(
                    index, command_type, ActionStatus.CANCELLED,
                    "Action execution was cancelled", started, command.get("command_data"),
                )
                results.append(result)
                self._notify(result)
                break

            if not bool(command.get("enabled", True)):
                result = self._result(
                    index, command_type, ActionStatus.SKIPPED,
                    "Action is disabled", started, command.get("command_data"),
                )
                results.append(result)
                self._notify(result)
                continue

            try:
                data = validate_command_data(command_type, command.get("command_data"))
                self.context.command_metadata = {
                    "command_id": command.get("id"),
                    "finger_id": command.get("finger_id"),
                    "finger_label": command.get("label", ""),
                }
                command["command_data"] = data
                self.executor(command, self.context)
                result = self._result(
                    index,
                    command_type,
                    ActionStatus.SUCCESS,
                    format_action_summary(command_type, data, command_type),
                    started,
                    data,
                )
            except CommandCancelledError as exc:
                result = self._result(
                    index, command_type, ActionStatus.CANCELLED,
                    str(exc), started, command.get("command_data"), error=str(exc),
                )
            except Exception as exc:
                result = self._result(
                    index, command_type, ActionStatus.FAILED,
                    str(exc), started, command.get("command_data"), error=str(exc),
                )

            results.append(result)
            self._notify(result)
            if result.status == ActionStatus.CANCELLED:
                break
            if result.status == ActionStatus.FAILED and self.error_policy == ErrorPolicy.STOP:
                break

        return RunReport(tuple(results))

    def _result(
        self,
        index: int,
        command_type: str,
        status: ActionStatus,
        message: str,
        started: float,
        command_data: Any,
        *,
        error: str | None = None,
    ) -> ActionResult:
        return ActionResult(
            index=index,
            command_type=command_type,
            status=status,
            message=message,
            duration_seconds=max(0.0, perf_counter() - started),
            command_data=dict(command_data) if isinstance(command_data, dict) else {},
            error=error,
        )

    def _notify(self, result: ActionResult) -> None:
        if self.on_result is not None:
            self.on_result(result)
