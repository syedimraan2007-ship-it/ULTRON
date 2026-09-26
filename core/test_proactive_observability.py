import pytest

from core.events import Event, EventType
from core.proactive_activity_guard import ProactiveActivityGuard
from core.proactive_consumer import ProactiveConsumer
from core.proactive_cooldown import ProactiveCooldown
from core.proactive_dispatcher import ProactiveDispatcher
from core.proactive_event_queue import ProactiveEventQueue
from core.proactive_policy import ProactivePolicy
from core.proactive_presenter import ProactivePresenter
from core.proactive_relevance import ProactiveRelevance


def _event(application="Code.exe"):
    return Event(
        EventType.PROACTIVE_DESKTOP_EVENT,
        {
            "event": "desktop_changed",
            "reason": "meaningful_change",
            "application": application,
            "window_title": "main.py",
        },
    )


def _dispatcher():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    guard.set_idle()
    dispatcher = ProactiveDispatcher(
        ProactiveConsumer(queue, guard),
        ProactivePresenter(guard),
    )
    return dispatcher, queue


def test_presented_decision_contains_only_bounded_public_fields():
    dispatcher, queue = _dispatcher()
    queue.push(_event())

    assert dispatcher.dispatch_once() is not None
    decision = dispatcher.last_decision()

    assert decision.status == "presented"
    assert decision.application == "Code.exe"
    assert decision.window_title == "main.py"
    assert decision.message == "Code editor is active."
    assert decision.reason == "presented"
    assert decision.reasoner_reason == ""


def test_cooldown_decision_is_recorded_before_consumer_access():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)
    cooldown.record()
    consumer_calls = []

    class Consumer:
        def consume_next(self):
            consumer_calls.append(True)
            return None

    dispatcher = ProactiveDispatcher(Consumer(), object(), cooldown=cooldown)

    assert dispatcher.dispatch_once() is None
    assert dispatcher.last_decision().status == "cooldown"
    assert consumer_calls == []


def test_no_candidate_and_irrelevant_decisions_are_recorded():
    dispatcher, _queue = _dispatcher()
    assert dispatcher.dispatch_once() is None
    assert dispatcher.last_decision().status == "no_candidate"

    class Consumer:
        def consume_next(self):
            return {
                "message": "Desktop is active.",
                "application": "explorer.exe",
                "window_title": "Desktop",
            }

    irrelevant = ProactiveDispatcher(
        Consumer(),
        object(),
        relevance=ProactiveRelevance(),
    )
    assert irrelevant.dispatch_once() is None
    assert irrelevant.last_decision().status == "irrelevant"
    assert irrelevant.last_decision().application == "explorer.exe"


def test_policy_rejection_is_observable():
    candidate = {
        "message": "Code editor is active.",
        "application": "Code.exe",
        "window_title": "main.py",
    }

    class Consumer:
        def consume_next(self):
            return candidate

    class Presenter:
        def present(self, value):
            return value

    class Policy:
        def allow(self, _value):
            return False

    dispatcher = ProactiveDispatcher(Consumer(), Presenter(), policy=Policy())

    assert dispatcher.dispatch_once() is None
    assert dispatcher.last_decision().status == "rejected"
    assert dispatcher.last_decision().reason == "policy_rejected"


def test_reasoner_rejection_contains_safe_reasoner_reason():
    candidate = {
        "message": "Code editor is active.",
        "application": "Code.exe",
        "window_title": "main.py",
    }

    class Consumer:
        def consume_next(self):
            return candidate

    class Presenter:
        def present(self, value):
            return value

    class Reasoner:
        def evaluate(self, _value):
            return {
                "should_speak": False,
                "message": "",
                "reason": "trivial_change",
            }

    dispatcher = ProactiveDispatcher(Consumer(), Presenter(), reasoner=Reasoner())

    assert dispatcher.dispatch_once() is None
    assert dispatcher.last_decision().status == "reasoner_rejected"
    assert dispatcher.last_decision().reasoner_reason == "trivial_change"


def test_exceptions_record_rejected_without_exposing_details():
    class Consumer:
        def consume_next(self):
            raise RuntimeError("private process_id=1234 stack trace")

    dispatcher = ProactiveDispatcher(Consumer(), object())

    assert dispatcher.dispatch_once() is None
    decision = dispatcher.last_decision()
    assert decision.status == "rejected"
    assert "1234" not in repr(decision)
    assert "stack trace" not in repr(decision).casefold()


def test_decision_is_immutable_and_bounded():
    from core.proactive_observability import ProactiveDecision

    decision = ProactiveDecision(
        "presented",
        "A" * 1000,
        "B" * 1000,
        "C" * 1000,
        "D" * 1000,
        "E" * 1000,
    )

    assert len(decision.application) == 256
    assert len(decision.window_title) == 256
    assert len(decision.message) == 512
    assert len(decision.reason) == 128
    assert len(decision.reasoner_reason) == 128
    with pytest.raises(Exception):
        decision.status = "rejected"


def test_latest_decision_is_replaced_per_attempt():
    dispatcher, queue = _dispatcher()
    assert dispatcher.last_decision() is None
    queue.push(_event())
    dispatcher.dispatch_once()
    first = dispatcher.last_decision()
    dispatcher.dispatch_once()
    second = dispatcher.last_decision()

    assert first.status == "presented"
    assert second.status == "no_candidate"