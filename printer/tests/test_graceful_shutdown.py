from __future__ import annotations

import signal
import threading
import importlib

from flask import Flask

app_module = importlib.import_module("printer_service.app")


class _FakeServer:
    def __init__(self, handlers: dict[int, object]) -> None:
        self.handlers = handlers
        self.shutdown_called = threading.Event()
        self.closed = False

    def serve_forever(self) -> None:
        handler = self.handlers[signal.SIGTERM]
        assert callable(handler)
        handler(signal.SIGTERM, None)
        assert self.shutdown_called.wait(timeout=1)

    def shutdown(self) -> None:
        self.shutdown_called.set()

    def server_close(self) -> None:
        self.closed = True


def test_production_server_handles_sigterm(monkeypatch, capsys) -> None:
    handlers: dict[int, object] = {}
    fake_server = _FakeServer(handlers)

    monkeypatch.setattr(app_module, "make_server", lambda *_args, **_kwargs: fake_server)

    def fake_signal(received_signal: int, handler: object) -> object:
        previous = handlers.get(received_signal, signal.SIG_DFL)
        handlers[received_signal] = handler
        return previous

    monkeypatch.setattr(app_module.signal, "signal", fake_signal)

    app_module._serve_production(Flask("shutdown-test"), "127.0.0.1", 8099)

    assert fake_server.shutdown_called.is_set()
    assert fake_server.closed
    output = capsys.readouterr().out
    assert '"event": "service.started"' in output
    assert '"event": "service.shutdown.started"' in output
    assert '"event": "service.shutdown.completed"' in output
