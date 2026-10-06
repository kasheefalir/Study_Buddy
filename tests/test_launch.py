from app import launch


class Process:
    def __init__(self):
        self.stopped = False

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return None

    def terminate(self):
        self.stopped = True


class PortProbe:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def bind(self, address):
        pass


def test_reuses_running_service_and_preloads_before_app(monkeypatch):
    calls = []
    monkeypatch.setattr(launch.sys, "argv", ["launch"])
    monkeypatch.setattr(launch.socket, "socket", PortProbe)
    monkeypatch.setattr(launch, "service_ready", lambda: True)

    def api(path, payload=None, timeout=5):
        calls.append(path)
        return {"models": [{"name": launch.settings.ollama_model}]}

    monkeypatch.setattr(launch, "ollama_request", api)
    monkeypatch.setattr(launch.subprocess, "Popen", lambda args, **kwargs: calls.append("uvicorn") or Process())
    assert launch.main() == 0
    assert calls == ["/api/tags", "/api/generate", "uvicorn"]


def test_missing_model_downloaded_before_preload(monkeypatch):
    calls = []
    monkeypatch.setattr(launch.sys, "argv", ["launch"])
    monkeypatch.setattr(launch.socket, "socket", PortProbe)
    monkeypatch.setattr(launch, "service_ready", lambda: True)
    monkeypatch.setattr(launch, "ollama_request", lambda path, payload=None, timeout=5: calls.append(path) or {})
    monkeypatch.setattr(launch.subprocess, "Popen", lambda *args, **kwargs: Process())
    assert launch.main() == 0
    assert calls == ["/api/tags", "/api/pull", "/api/generate"]


def test_port_conflict_does_not_start_ollama(monkeypatch):
    class BusyPort(PortProbe):
        def bind(self, address):
            raise OSError("in use")
    monkeypatch.setattr(launch.sys, "argv", ["launch"])
    monkeypatch.setattr(launch.socket, "socket", BusyPort)
    monkeypatch.setattr(launch, "service_ready", lambda: (_ for _ in ()).throw(AssertionError("must not probe Ollama")))
    assert launch.main() == 1
