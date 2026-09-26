from core.desktop_context_tracker import DesktopContextTracker


def _context(application="Code.exe", title="main.py", process_id=100):
    return {
        "active_window": {
            "application": application,
            "window_title": title,
            "process_id": process_id,
        },
        "timestamp": "2026-09-19T12:00:00+00:00",
    }


def test_first_snapshot_is_not_reported_as_changed():
    result = DesktopContextTracker().update(_context())

    assert result["is_first"] is True
    assert result["changed"] is False
    assert result["previous"] is None
    assert result["current"] == {
        "application": "Code.exe",
        "window_title": "main.py",
        "process_id": 100,
    }


def test_timestamp_only_change_is_ignored():
    tracker = DesktopContextTracker()
    tracker.update(_context())

    updated = _context()
    updated["timestamp"] = "2026-09-19T12:01:00+00:00"
    result = tracker.update(updated)

    assert result["is_first"] is False
    assert result["changed"] is False


def test_window_title_change_is_detected():
    tracker = DesktopContextTracker()
    tracker.update(_context())

    result = tracker.update(_context(title="other.py"))

    assert result["changed"] is True
    assert result["previous"]["window_title"] == "main.py"
    assert result["current"]["window_title"] == "other.py"


def test_application_change_is_detected():
    tracker = DesktopContextTracker()
    tracker.update(_context())

    result = tracker.update(_context(application="PowerShell.exe"))

    assert result["changed"] is True
    assert result["current"]["application"] == "PowerShell.exe"


def test_process_id_change_is_detected():
    tracker = DesktopContextTracker()
    tracker.update(_context())

    result = tracker.update(_context(process_id=200))

    assert result["changed"] is True
    assert result["current"]["process_id"] == 200


def test_missing_values_are_normalized_deterministically():
    tracker = DesktopContextTracker()

    first = tracker.update({"active_window": {}, "timestamp": "one"})
    second = tracker.update({"active_window": {}, "timestamp": "two"})

    expected = {
        "application": None,
        "window_title": None,
        "process_id": None,
    }
    assert first["current"] == expected
    assert second["current"] == expected
    assert second["changed"] is False


def test_updates_compare_against_the_immediately_previous_snapshot():
    tracker = DesktopContextTracker()
    tracker.update(_context(title="first.py"))
    tracker.update(_context(title="second.py"))

    result = tracker.update(_context(title="third.py"))

    assert result["changed"] is True
    assert result["previous"]["window_title"] == "second.py"
    assert result["current"]["window_title"] == "third.py"
