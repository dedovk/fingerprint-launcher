import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from services import timer_manager as timer_module
from services.timer_manager import TimerManager


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_timer_manager_tracks_and_finishes_timer(monkeypatch):
    app = _app()
    now = [100.0]
    monkeypatch.setattr(timer_module, "monotonic", lambda: now[0])
    manager = TimerManager()
    started = []
    finished = []
    changes = []
    manager.timer_started.connect(started.append)
    manager.timer_finished.connect(finished.append)
    manager.timers_changed.connect(changes.append)

    manager._schedule({
        "duration_ms": 2_000,
        "message": "Tea",
        "sound_path": "",
        "command_id": 7,
    })
    assert started[0]["remaining_ms"] == 2_000
    assert manager.snapshots()[0]["command_id"] == 7

    now[0] = 102.0
    manager._tick()
    assert len(finished) == 1
    assert finished[0]["message"] == "Tea"
    assert manager.snapshots() == []
    assert changes[-1] == []
    assert not manager._tick_timer.isActive()
    manager.deleteLater()
    app.processEvents()


def test_timer_manager_can_cancel_one_or_all(monkeypatch):
    app = _app()
    monkeypatch.setattr(timer_module, "monotonic", lambda: 50.0)
    manager = TimerManager()
    cancelled = []
    manager.timer_cancelled.connect(cancelled.append)
    manager._schedule({"duration_ms": 1_000, "message": "One"})
    manager._schedule({"duration_ms": 2_000, "message": "Two"})

    timer_id = manager.snapshots()[0]["timer_id"]
    assert manager.cancel_timer(timer_id)
    assert not manager.cancel_timer("missing")
    manager.cancel_all()

    assert len(cancelled) == 2
    assert manager.snapshots() == []
    manager.deleteLater()
    app.processEvents()
