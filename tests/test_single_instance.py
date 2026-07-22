import os
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtWidgets import QApplication

import main as app_main


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_second_instance_notifies_the_existing_instance(monkeypatch):
    app = _app()
    server_name = f"FingerprintLauncher-test-{uuid4().hex}"
    monkeypatch.setattr(app_main, "SINGLE_INSTANCE_NAME", server_name)
    first = app_main.SingleInstance()
    activations = []
    second_results = []
    first.activation_requested.connect(lambda: activations.append(True))

    try:
        assert first.acquire_or_notify()
        def launch_second():
            second = app_main.SingleInstance()
            second_results.append(second.acquire_or_notify())
            second.close()

        thread = Thread(target=launch_second)
        thread.start()
        deadline = monotonic() + 2
        while thread.is_alive() and monotonic() < deadline:
            app.processEvents()
            sleep(0.01)
        thread.join(timeout=1)
        app.processEvents()
        assert second_results == [False]
        assert activations == [True]
    finally:
        first.close()
        QLocalServer.removeServer(server_name)
        first.deleteLater()
        app.processEvents()
