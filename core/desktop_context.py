"""Normalize desktop-awareness metadata into a stable context snapshot."""

from datetime import datetime, timezone

from core.desktop_awareness import get_active_window


_CONTEXT_KEYS = (
    "application",
    "window_title",
    "process_id",
)


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_context(timestamp: str) -> dict[str, object]:
    return {
        "active_window": {
            key: None
            for key in _CONTEXT_KEYS
        },
        "timestamp": timestamp,
    }


def get_desktop_context() -> dict[str, object]:
    """Return a stable, read-only snapshot of the active desktop window."""

    fallback_timestamp = _current_timestamp()

    try:
        active_window = get_active_window()
    except Exception:
        return _empty_context(fallback_timestamp)

    if not isinstance(active_window, dict):
        return _empty_context(fallback_timestamp)

    timestamp = active_window.get("timestamp")

    if not isinstance(timestamp, str) or not timestamp:
        timestamp = fallback_timestamp

    return {
        "active_window": {
            key: active_window.get(key)
            for key in _CONTEXT_KEYS
        },
        "timestamp": timestamp,
    }
