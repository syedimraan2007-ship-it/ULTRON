from copy import deepcopy

from core.proactive_activity_guard import ProactiveActivityGuard
from core.proactive_presenter import ProactivePresenter


def _candidate(**overrides):
    candidate = {
        "event": "desktop_changed",
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    candidate.update(overrides)
    return candidate


def _idle_presenter():
    guard = ProactiveActivityGuard()
    guard.set_idle()
    return ProactivePresenter(guard), guard


def test_valid_candidate_and_idle_returns_presentation_payload():
    presenter, _guard = _idle_presenter()

    result = presenter.present(_candidate())

    assert result == {
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }


def test_blocked_activity_returns_none():
    guard = ProactiveActivityGuard()
    presenter = ProactivePresenter(guard)

    assert presenter.present(_candidate()) is None


def test_malformed_candidate_returns_none():
    presenter, _guard = _idle_presenter()

    assert presenter.present(None) is None
    assert presenter.present({"event": "other"}) is None


def test_missing_user_facing_field_returns_none():
    presenter, _guard = _idle_presenter()

    for field in ("message", "application", "window_title"):
        candidate = _candidate()
        candidate.pop(field)
        assert presenter.present(candidate) is None


def test_output_is_bounded_and_has_exact_schema():
    presenter, _guard = _idle_presenter()
    oversized = "x" * 1000

    result = presenter.present(
        _candidate(
            message=oversized,
            application=oversized,
            window_title=oversized,
        )
    )

    assert result is not None
    assert set(result) == {"message", "application", "window_title"}
    assert len(result["message"]) == 512
    assert len(result["application"]) == 256
    assert len(result["window_title"]) == 256


def test_candidate_is_not_mutated():
    presenter, _guard = _idle_presenter()
    candidate = _candidate()
    before = deepcopy(candidate)

    presenter.present(candidate)

    assert candidate == before


def test_presenter_does_not_change_guard_state():
    presenter, guard = _idle_presenter()
    before = guard.state

    presenter.present(_candidate())

    assert guard.state is before


def test_presenter_does_not_call_llm_tts_or_speech(monkeypatch):
    calls = []
    presenter, _guard = _idle_presenter()
    monkeypatch.setattr(
        "core.ultron.chat",
        lambda **_kwargs: calls.append("llm"),
    )
    monkeypatch.setattr(
        "core.ultron.speak",
        lambda *_args, **_kwargs: calls.append("tts"),
    )

    presenter.present(_candidate())

    assert calls == []


def test_presenter_has_no_event_bus_subscription_or_automatic_work():
    presenter, _guard = _idle_presenter()

    assert not hasattr(presenter, "subscribe")
    assert not hasattr(presenter, "poll")
    assert not hasattr(presenter, "start")


def test_runtime_presenter_uses_existing_activity_guard():
    import core.ultron as ultron

    assert (
        ultron._PROACTIVE_PRESENTER._activity_guard
        is ultron._PROACTIVE_ACTIVITY_GUARD
    )