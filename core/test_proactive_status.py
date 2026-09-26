from core import ultron
from core.proactive_observability import ProactiveDecision


def test_unavailable_runtime_returns_safe_empty_status(monkeypatch):
    monkeypatch.setattr(ultron, "_PROACTIVE_REASONER", None)

    assert ultron.get_proactive_status() == {
        "available": False,
        "last_decision": None,
    }


def test_partially_unavailable_runtime_returns_safe_empty_status(monkeypatch):
    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", None)

    assert ultron.get_proactive_status() == {
        "available": False,
        "last_decision": None,
    }


def test_initialized_runtime_with_no_decision_returns_none_decision(monkeypatch):
    class Dispatcher:
        def last_decision(self):
            return None

    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", Dispatcher())

    result = ultron.get_proactive_status()

    assert result == {"available": True, "last_decision": None}


def test_presented_decision_is_projected_from_dispatcher_state(monkeypatch):
    decision = ProactiveDecision(
        "presented",
        "Code.exe",
        "main.py",
        "presented",
        "Code editor is active.",
        "desktop_context_change",
    )

    class Dispatcher:
        def last_decision(self):
            return decision

    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", Dispatcher())

    result = ultron.get_proactive_status()

    assert result == {
        "available": True,
        "last_decision": {
            "status": "presented",
            "application": "Code.exe",
            "window_title": "main.py",
            "reason": "presented",
            "message": "Code editor is active.",
            "reasoner_reason": "desktop_context_change",
        },
    }


def test_cooldown_and_reasoner_rejection_statuses_are_exposed(monkeypatch):
    decisions = iter([
        ProactiveDecision("cooldown", reason="cooldown"),
        ProactiveDecision(
            "reasoner_rejected",
            "Code.exe",
            "main.py",
            "reasoner_rejected",
            "Code editor is active.",
            "trivial_change",
        ),
    ])

    class Dispatcher:
        def last_decision(self):
            return next(decisions)

    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", Dispatcher())

    assert ultron.get_proactive_status()["last_decision"]["status"] == "cooldown"
    assert ultron.get_proactive_status()["last_decision"]["status"] == "reasoner_rejected"


def test_returned_status_is_fresh_and_cannot_mutate_internal_state(monkeypatch):
    decision = ProactiveDecision("presented", "Code.exe", "main.py", "presented", "Code editor is active.")

    class Dispatcher:
        def last_decision(self):
            return decision

    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", Dispatcher())
    first = ultron.get_proactive_status()
    first["last_decision"]["message"] = "changed"
    second = ultron.get_proactive_status()

    assert first is not second
    assert second["last_decision"]["message"] == "Code editor is active."


def test_status_has_only_safe_bounded_public_fields(monkeypatch):
    decision = ProactiveDecision(
        "presented",
        "A" * 1000,
        "B" * 1000,
        "C" * 1000,
        "D" * 1000,
        "E" * 1000,
    )

    class Dispatcher:
        def last_decision(self):
            return decision

    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", Dispatcher())
    result = ultron.get_proactive_status()
    public = result["last_decision"]

    assert set(result) == {"available", "last_decision"}
    assert set(public) == {
        "status",
        "application",
        "window_title",
        "reason",
        "message",
        "reasoner_reason",
    }
    assert len(public["application"]) == 256
    assert len(public["window_title"]) == 256
    assert len(public["message"]) == 512
    assert len(public["reason"]) == 128
    assert len(public["reasoner_reason"]) == 128
    assert "process_id" not in public
    assert "queue" not in public
    assert "prompt" not in public