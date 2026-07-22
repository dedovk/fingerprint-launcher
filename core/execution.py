"""Shared cancellation primitives for action execution."""

from __future__ import annotations

from threading import Event
from typing import Any, Callable


class CommandCancelledError(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        """Wait up to timeout seconds and return True if cancellation occurred."""
        return self._event.wait(max(0.0, timeout))


TimerScheduler = Callable[[dict[str, Any]], None]


class ExecutionContext:
    def __init__(
        self,
        token: CancellationToken | None = None,
        timer_scheduler: TimerScheduler | None = None,
    ) -> None:
        self.token = token or CancellationToken()
        self.timer_scheduler = timer_scheduler
        self.command_metadata: dict[str, Any] = {}

    def check_cancelled(self) -> None:
        if self.token.is_cancelled:
            raise CommandCancelledError("Action execution was cancelled")

    def sleep(self, seconds: float) -> None:
        self.check_cancelled()
        if seconds > 0 and self.token.wait(seconds):
            raise CommandCancelledError("Action execution was cancelled")

    def schedule_timer(self, data: dict[str, Any]) -> None:
        self.check_cancelled()
        if self.timer_scheduler is None:
            raise RuntimeError("Timer service is unavailable")
        self.timer_scheduler({**dict(data), **self.command_metadata})
