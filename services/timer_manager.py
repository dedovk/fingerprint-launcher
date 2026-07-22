"""Application-lifetime quick timers owned by the Qt GUI thread."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic
from uuid import uuid4

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal, pyqtSlot


@dataclass
class TimerInstance:
    timer_id: str
    duration_ms: int
    deadline: float
    message: str = ""
    sound_path: str = ""
    command_id: int | None = None
    finger_id: int | None = None
    finger_label: str = ""

    def snapshot(self, now: float) -> dict:
        result = asdict(self)
        result["remaining_ms"] = max(0, round((self.deadline - now) * 1_000))
        return result


class TimerManager(QObject):
    schedule_requested = pyqtSignal(dict)
    timers_changed = pyqtSignal(list)
    timer_started = pyqtSignal(dict)
    timer_finished = pyqtSignal(dict)
    timer_cancelled = pyqtSignal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timers: dict[str, TimerInstance] = {}
        self._players: list[tuple[object, object]] = []
        self._last_display_second: int | None = None
        self.schedule_requested.connect(self._schedule)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(200)
        self._tick_timer.timeout.connect(self._tick)

    def request_timer(self, data: dict) -> None:
        """Thread-safe entry point used by action worker threads."""
        self.schedule_requested.emit(dict(data))

    @pyqtSlot(dict)
    def _schedule(self, data: dict) -> None:
        duration_ms = int(data["duration_ms"])
        instance = TimerInstance(
            timer_id=uuid4().hex,
            duration_ms=duration_ms,
            deadline=monotonic() + duration_ms / 1_000,
            message=str(data.get("message") or ""),
            sound_path=str(data.get("sound_path") or ""),
            command_id=self._optional_int(data.get("command_id")),
            finger_id=self._optional_int(data.get("finger_id")),
            finger_label=str(data.get("finger_label") or ""),
        )
        self._timers[instance.timer_id] = instance
        self._last_display_second = None
        if not self._tick_timer.isActive():
            self._tick_timer.start()
        snapshot = instance.snapshot(monotonic())
        self.timer_started.emit(snapshot)
        self._emit_changed()

    def cancel_timer(self, timer_id: str) -> bool:
        instance = self._timers.pop(timer_id, None)
        if instance is None:
            return False
        self.timer_cancelled.emit(instance.snapshot(monotonic()))
        self._after_collection_changed()
        return True

    def cancel_all(self) -> None:
        for timer_id in tuple(self._timers):
            self.cancel_timer(timer_id)

    def snapshots(self) -> list[dict]:
        now = monotonic()
        return sorted(
            (timer.snapshot(now) for timer in self._timers.values()),
            key=lambda item: (item["remaining_ms"], item["timer_id"]),
        )

    @pyqtSlot()
    def _tick(self) -> None:
        now = monotonic()
        finished = [
            timer_id
            for timer_id, timer in self._timers.items()
            if timer.deadline <= now
        ]
        for timer_id in finished:
            instance = self._timers.pop(timer_id)
            snapshot = instance.snapshot(now)
            self._play_sound(instance.sound_path)
            self.timer_finished.emit(snapshot)

        display_second = int(now)
        if finished or display_second != self._last_display_second:
            self._last_display_second = display_second
            self._emit_changed()
        if not self._timers:
            self._tick_timer.stop()

    def _after_collection_changed(self) -> None:
        self._last_display_second = None
        self._emit_changed()
        if not self._timers:
            self._tick_timer.stop()

    def _emit_changed(self) -> None:
        self.timers_changed.emit(self.snapshots())

    def _play_sound(self, sound_path: str) -> None:
        path = Path(sound_path)
        if not sound_path or not path.is_file():
            return
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

            audio = QAudioOutput(self)
            player = QMediaPlayer(self)
            player.setAudioOutput(audio)
            player.setSource(QUrl.fromLocalFile(str(path.resolve())))
            pair = (player, audio)
            self._players.append(pair)

            def cleanup(*_args) -> None:
                if pair in self._players:
                    self._players.remove(pair)
                player.deleteLater()
                audio.deleteLater()

            player.mediaStatusChanged.connect(
                lambda status: cleanup()
                if status == QMediaPlayer.MediaStatus.EndOfMedia
                else None
            )
            player.errorOccurred.connect(lambda *_: cleanup())
            player.play()
        except (ImportError, RuntimeError):
            return

    @staticmethod
    def _optional_int(value) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
