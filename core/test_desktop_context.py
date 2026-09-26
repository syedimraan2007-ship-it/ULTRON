from datetime import datetime

from core import desktop_context


def test_get_desktop_context_normalizes_active_window(monkeypatch):
    monkeypatch.setattr(
        desktop_context,
        "get_active_window",
        lambda: {
            "application": "Code.exe",
            "window_title": "ultron.py - Visual Studio Code",
            "process_id": 1234,
            "timestamp": "2026-09-19T12:00:00+00:00",
        },
    )

    result = desktop_context.get_desktop_context()

    assert result == {
        "active_window": {
            "application": "Code.exe",
            "window_title": "ultron.py - Visual Studio Code",
            "process_id": 1234,
        },
        "timestamp": "2026-09-19T12:00:00+00:00",
    }


def test_get_desktop_context_preserves_missing_window_fields(monkeypatch):
    monkeypatch.setattr(
        desktop_context,
        "get_active_window",
        lambda: {
            "application": None,
            "window_title": None,
            "process_id": None,
            "timestamp": "2026-09-19T12:00:00+00:00",
        },
    )

    result = desktop_context.get_desktop_context()

    assert result["active_window"] == {
        "application": None,
        "window_title": None,
        "process_id": None,
    }


def test_get_desktop_context_preserves_source_timestamp(monkeypatch):
    timestamp = "2026-09-19T12:34:56+00:00"
    monkeypatch.setattr(
        desktop_context,
        "get_active_window",
        lambda: {"timestamp": timestamp},
    )

    result = desktop_context.get_desktop_context()

    assert result["timestamp"] == timestamp


def test_get_desktop_context_falls_back_when_dependency_fails(monkeypatch):
    def raise_awareness_error():
        raise OSError("desktop metadata unavailable")

    monkeypatch.setattr(
        desktop_context,
        "get_active_window",
        raise_awareness_error,
    )

    result = desktop_context.get_desktop_context()

    assert result["active_window"] == {
        "application": None,
        "window_title": None,
        "process_id": None,
    }
    datetime.fromisoformat(result["timestamp"])


def test_get_desktop_context_has_stable_schema(monkeypatch):
    monkeypatch.setattr(
        desktop_context,
        "get_active_window",
        lambda: {
            "application": "PowerShell.exe",
            "window_title": "PowerShell",
            "process_id": 5678,
            "timestamp": "2026-09-19T12:00:00+00:00",
            "unrelated_field": "ignored",
        },
    )

    result = desktop_context.get_desktop_context()

    assert set(result) == {"active_window", "timestamp"}
    assert set(result["active_window"]) == {
        "application",
        "window_title",
        "process_id",
    }
