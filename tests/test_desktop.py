from app.desktop import bind_socket, data_directory
from app.desktop import setup_cloud_default
from dataclasses import replace
from app import config, launch


def test_cloud_setup_registers_without_generation(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, ollama_model="gemma4:31b-cloud"))
    calls = []
    def request(path, payload=None, timeout=5):
        calls.append((path, payload))
        return {}
    monkeypatch.setattr(launch, "ollama_request", request)
    assert "configured" in setup_cloud_default()
    assert calls == [("/api/tags", None), ("/api/pull", {"model": "gemma4:31b-cloud", "stream": False})]


def test_cloud_setup_failure_is_recoverable(monkeypatch):
    monkeypatch.setattr(config, "settings", replace(config.settings, ollama_model="gemma4:31b-cloud"))
    def unavailable(*args, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr(launch, "ollama_request", unavailable)
    assert "Retry model setup" in setup_cloud_default()


def test_desktop_data_is_outside_install_folder(monkeypatch, tmp_path):
    monkeypatch.setattr("app.desktop.sys.platform", "win32")
    monkeypatch.delenv("BUDDY_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert data_directory() == tmp_path / "Study Buddy" / "data"


def test_mac_data_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("BUDDY_DATA_DIR", raising=False)
    monkeypatch.setattr("app.desktop.sys.platform", "darwin")
    monkeypatch.setattr("app.desktop.Path.home", lambda: tmp_path)
    assert data_directory() == tmp_path / "Library/Application Support/Study Buddy/data"


def test_desktop_instance_lock(tmp_path):
    import pytest
    from app.desktop import acquire_lock
    first = acquire_lock(tmp_path)
    try:
        with pytest.raises(OSError):
            acquire_lock(tmp_path)
    finally:
        first.close()
    acquire_lock(tmp_path).close()


def test_desktop_respects_explicit_data_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BUDDY_DATA_DIR", str(tmp_path / "existing"))
    assert data_directory() == tmp_path / "existing"


def test_desktop_reserves_distinct_loopback_ports():
    first = bind_socket()
    try:
        second = bind_socket()
        try:
            assert first.getsockname()[0] == second.getsockname()[0] == "127.0.0.1"
            assert first.getsockname()[1] != second.getsockname()[1]
        finally:
            second.close()
    finally:
        first.close()
