from core.proactive_engine import ProactiveEngine


def _change(
    *,
    is_first=False,
    changed=True,
    application="Code.exe",
    window_title="main.py",
):
    return {
        "is_first": is_first,
        "changed": changed,
        "previous": {
            "application": "Previous.exe",
            "window_title": "previous.py",
            "process_id": 99,
        },
        "current": {
            "application": application,
            "window_title": window_title,
            "process_id": 100,
        },
    }


def test_first_observation_is_not_eligible():
    result = ProactiveEngine().evaluate(_change(is_first=True, changed=False))

    assert result == {
        "eligible": False,
        "reason": "first_observation",
        "event": "desktop_changed",
    }


def test_unchanged_context_is_not_eligible():
    result = ProactiveEngine().evaluate(_change(changed=False))

    assert result["eligible"] is False
    assert result["reason"] == "unchanged"


def test_application_change_is_eligible():
    result = ProactiveEngine().evaluate(_change(application="PowerShell.exe"))

    assert result["eligible"] is True
    assert result["reason"] == "meaningful_change"


def test_window_title_change_is_eligible():
    result = ProactiveEngine().evaluate(_change(window_title="other.py"))

    assert result["eligible"] is True


def test_missing_or_unknown_context_is_not_eligible():
    engine = ProactiveEngine()

    missing = engine.evaluate(_change(application=None))
    unknown = engine.evaluate(
        {
            "is_first": False,
            "changed": True,
            "previous": None,
            "current": None,
        }
    )

    assert missing["eligible"] is False
    assert missing["reason"] == "unknown_context"
    assert unknown["eligible"] is False
    assert unknown["reason"] == "unknown_context"


def test_cooldown_blocks_repeated_eligible_events():
    now = [10.0]
    engine = ProactiveEngine(cooldown_seconds=30.0, clock=lambda: now[0])

    assert engine.evaluate(_change())["eligible"] is True
    now[0] = 20.0
    result = engine.evaluate(_change(window_title="other.py"))

    assert result["eligible"] is False
    assert result["reason"] == "cooldown"


def test_new_meaningful_change_is_eligible_after_cooldown():
    now = [10.0]
    engine = ProactiveEngine(cooldown_seconds=30.0, clock=lambda: now[0])
    engine.evaluate(_change())

    now[0] = 40.0
    result = engine.evaluate(_change(window_title="other.py"))

    assert result["eligible"] is True


def test_timestamp_only_difference_does_not_trigger_eligibility():
    engine = ProactiveEngine()
    change = _change(changed=False)
    change["timestamp"] = "2026-09-19T12:01:00+00:00"

    result = engine.evaluate(change)

    assert result["eligible"] is False
    assert result["reason"] == "unchanged"


def test_process_id_only_change_is_not_eligible():
    change = _change()
    change["current"]["application"] = "Previous.exe"
    change["current"]["window_title"] = "previous.py"
    change["current"]["process_id"] = 200

    result = ProactiveEngine().evaluate(change)

    assert result["eligible"] is False
    assert result["reason"] == "unknown_context"


def test_engine_instances_do_not_share_cooldown_state():
    now = [10.0]
    first = ProactiveEngine(cooldown_seconds=30.0, clock=lambda: now[0])
    second = ProactiveEngine(cooldown_seconds=30.0, clock=lambda: now[0])

    assert first.evaluate(_change())["eligible"] is True
    assert second.evaluate(_change())["eligible"] is True