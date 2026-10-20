from app.desktop import bind_socket, data_directory


def test_desktop_data_is_outside_install_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("BUDDY_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert data_directory() == tmp_path / "Study Buddy" / "data"


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
