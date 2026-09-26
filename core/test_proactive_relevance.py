from copy import deepcopy

from core.proactive_relevance import ProactiveRelevance


def _candidate(**overrides):
    candidate = {
        "event": "desktop_changed",
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    candidate.update(overrides)
    return candidate


def test_normal_application_is_relevant():
    assert ProactiveRelevance().is_relevant(_candidate()) is True


def test_normal_title_is_relevant():
    assert ProactiveRelevance().is_relevant(
        _candidate(window_title="project notes")
    ) is True


def test_none_and_malformed_candidates_are_rejected():
    relevance = ProactiveRelevance()

    assert relevance.is_relevant(None) is False
    assert relevance.is_relevant([]) is False
    assert relevance.is_relevant({"event": "desktop_changed"}) is False


def test_wrong_event_is_rejected():
    assert ProactiveRelevance().is_relevant(_candidate(event="other")) is False


def test_missing_required_fields_are_rejected():
    relevance = ProactiveRelevance()
    for field in ("application", "window_title", "message"):
        candidate = _candidate()
        candidate.pop(field)
        assert relevance.is_relevant(candidate) is False


def test_empty_application_or_title_is_rejected():
    relevance = ProactiveRelevance()

    assert relevance.is_relevant(_candidate(application=" ")) is False
    assert relevance.is_relevant(_candidate(window_title="")) is False
    assert relevance.is_relevant(_candidate(application="unknown")) is False


def test_over_limit_strings_are_rejected():
    relevance = ProactiveRelevance()

    assert relevance.is_relevant(
        _candidate(message="x" * 513)
    ) is False
    assert relevance.is_relevant(
        _candidate(application="x" * 257)
    ) is False
    assert relevance.is_relevant(
        _candidate(window_title="x" * 257)
    ) is False


def test_shell_transitions_are_rejected():
    relevance = ProactiveRelevance()

    assert relevance.is_relevant(_candidate(application="explorer.exe")) is False
    assert relevance.is_relevant(_candidate(window_title="Desktop")) is False


def test_lock_and_security_transitions_are_rejected():
    relevance = ProactiveRelevance()

    assert relevance.is_relevant(_candidate(application="LockApp.exe")) is False
    assert relevance.is_relevant(_candidate(window_title="Windows Sign-in")) is False


def test_transient_system_ui_is_rejected():
    relevance = ProactiveRelevance()

    assert relevance.is_relevant(_candidate(application="SearchHost.exe")) is False
    assert relevance.is_relevant(_candidate(application="TextInputHost.exe")) is False


def test_candidate_is_not_mutated():
    relevance = ProactiveRelevance()
    candidate = _candidate()
    before = deepcopy(candidate)

    assert relevance.is_relevant(candidate) is True
    assert candidate == before