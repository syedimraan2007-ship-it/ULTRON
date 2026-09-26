from datetime import datetime

from core import desktop_awareness


def test_get_active_window_returns_structured_metadata(monkeypatch):
    monkeypatch.setattr(
        desktop_awareness,
        "_get_foreground_window",
        lambda: 123,
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_window_title",
        lambda window_handle: "ultron.py - Visual Studio Code",
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_process_id",
        lambda window_handle: 456,
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_process_name",
        lambda process_id: "Code.exe",
    )

    result = desktop_awareness.get_active_window()

    assert result["application"] == "Code.exe"
    assert result["window_title"] == "ultron.py - Visual Studio Code"
    assert result["process_id"] == 456
    datetime.fromisoformat(result["timestamp"])


def test_process_lookup_is_used_for_application_name(monkeypatch):
    observed = {}

    monkeypatch.setattr(
        desktop_awareness,
        "_get_foreground_window",
        lambda: 123,
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_window_title",
        lambda window_handle: "PowerShell",
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_process_id",
        lambda window_handle: 789,
    )

    def fake_process_name(process_id):
        observed["process_id"] = process_id
        return "WindowsTerminal.exe"

    monkeypatch.setattr(
        desktop_awareness,
        "_get_process_name",
        fake_process_name,
    )

    result = desktop_awareness.get_active_window()

    assert observed == {"process_id": 789}
    assert result["application"] == "WindowsTerminal.exe"


def test_missing_window_handle_returns_empty_metadata(monkeypatch):
    monkeypatch.setattr(
        desktop_awareness,
        "_get_foreground_window",
        lambda: None,
    )

    result = desktop_awareness.get_active_window()

    assert result["application"] is None
    assert result["window_title"] is None
    assert result["process_id"] is None
    assert result["timestamp"]


def test_process_lookup_failure_preserves_window_metadata(monkeypatch):
    monkeypatch.setattr(
        desktop_awareness,
        "_get_foreground_window",
        lambda: 123,
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_window_title",
        lambda window_handle: "Settings",
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_process_id",
        lambda window_handle: 321,
    )
    monkeypatch.setattr(
        desktop_awareness,
        "_get_process_name",
        lambda process_id: None,
    )

    result = desktop_awareness.get_active_window()

    assert result["window_title"] == "Settings"
    assert result["process_id"] == 321
    assert result["application"] is None


def test_windows_metadata_failure_returns_structured_fallback(monkeypatch):
    def raise_metadata_error():
        raise OSError("Windows metadata unavailable")

    monkeypatch.setattr(
        desktop_awareness,
        "_get_foreground_window",
        raise_metadata_error,
    )

    result = desktop_awareness.get_active_window()

    assert result["application"] is None
    assert result["window_title"] is None
    assert result["process_id"] is None
    assert result["timestamp"]
