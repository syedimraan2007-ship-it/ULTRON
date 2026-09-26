from copy import deepcopy

from core.events import Event, EventType
from core.proactive_activity_guard import ProactiveActivityGuard
from core.proactive_consumer import ProactiveConsumer
from core.proactive_cooldown import ProactiveCooldown
from core.proactive_dispatcher import ProactiveDispatcher
from core.proactive_dispatch_result import ProactiveDispatchResult
from core.proactive_event_queue import ProactiveEventQueue
from core.proactive_presenter import ProactivePresenter
from core.proactive_relevance import ProactiveRelevance
from core.proactive_policy import ProactivePolicy
from core.proactive_reasoner import ProactiveReasoner


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


def _dispatcher(queue=None, guard=None):
    if queue is None:
        queue = ProactiveEventQueue()
    if guard is None:
        guard = ProactiveActivityGuard()
    return (
        ProactiveDispatcher(
            ProactiveConsumer(queue, guard),
            ProactivePresenter(guard),
        ),
        queue,
        guard,
    )


def test_empty_queue_returns_none():
    dispatcher, _queue, guard = _dispatcher()
    guard.set_idle()

    assert dispatcher.dispatch_once() is None


def test_blocked_activity_keeps_event_queued():
    dispatcher, queue, _guard = _dispatcher()
    queue.push(_event())

    assert dispatcher.dispatch_once() is None
    assert len(queue) == 1


def test_idle_valid_event_returns_payload_and_removes_one_event():
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event())

    result = dispatcher.dispatch_once()

    assert result == {
        "message": "Code editor is active.",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    assert len(queue) == 0


def test_malformed_event_is_safe_and_remains_queued():
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue._events.append({"event": "invalid"})

    assert dispatcher.dispatch_once() is None
    assert len(queue) == 1


def test_presenter_rejection_returns_none():
    calls = []

    class FakeConsumer:
        def consume_next(self):
            return {"event": "desktop_changed"}

    class RejectingPresenter:
        def present(self, candidate):
            calls.append(candidate)
            return None

    result = ProactiveDispatcher(FakeConsumer(), RejectingPresenter()).dispatch_once()

    assert result is None
    assert len(calls) == 1


def test_consumer_exception_returns_none():
    class BrokenConsumer:
        def consume_next(self):
            raise RuntimeError("consumer failure")

    class UnexpectedPresenter:
        def present(self, _candidate):
            raise AssertionError("presenter must not be called")

    assert ProactiveDispatcher(
        BrokenConsumer(),
        UnexpectedPresenter(),
    ).dispatch_once() is None


def test_presenter_exception_returns_none():
    class FakeConsumer:
        def consume_next(self):
            return {"event": "desktop_changed"}

    class BrokenPresenter:
        def present(self, _candidate):
            raise RuntimeError("presenter failure")

    assert ProactiveDispatcher(FakeConsumer(), BrokenPresenter()).dispatch_once() is None


def test_dispatch_processes_exactly_one_event_per_call():
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event("first"))
    queue.push(_event("second"))

    result = dispatcher.dispatch_once()

    assert result["application"] == "first"
    assert len(queue) == 1
    assert queue.peek()["application"] == "second"


def test_fifo_order_is_preserved():
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event("first"))
    queue.push(_event("second"))

    assert dispatcher.dispatch_once()["application"] == "first"
    assert dispatcher.dispatch_once()["application"] == "second"


def test_candidate_and_output_are_not_mutated():
    candidate = {
        "event": "desktop_changed",
        "message": "candidate",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    before = deepcopy(candidate)
    output = {"message": "presented"}

    class FakeConsumer:
        def consume_next(self):
            return candidate

    class FakePresenter:
        def present(self, received):
            received["message"] = "mutated copy"
            return {
                "message": output["message"],
                "application": "Code.exe",
                "window_title": "main.py",
            }

    result = ProactiveDispatcher(FakeConsumer(), FakePresenter()).dispatch_once()

    assert result == {
        "message": "presented",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    assert candidate == before
    assert output == {"message": "presented"}


def test_dispatch_does_not_change_guard_state():
    dispatcher, _queue, guard = _dispatcher()
    guard.set_idle()
    before = guard.state

    dispatcher.dispatch_once()

    assert guard.state is before


def test_becoming_idle_does_not_automatically_dispatch():
    dispatcher, queue, guard = _dispatcher()
    queue.push(_event())

    guard.set_idle()

    assert len(queue) == 1
    assert dispatcher.dispatch_once() is not None


def test_dispatcher_has_no_event_bus_or_scheduler_api():
    dispatcher, _queue, _guard = _dispatcher()

    assert not hasattr(dispatcher, "subscribe")
    assert not hasattr(dispatcher, "emit")
    assert not hasattr(dispatcher, "poll")
    assert not hasattr(dispatcher, "start")


def test_dispatcher_does_not_call_llm_tts_or_other_actions(monkeypatch):
    calls = []
    dispatcher, _queue, guard = _dispatcher()
    guard.set_idle()
    monkeypatch.setattr("core.ultron.chat", lambda **_kwargs: calls.append("llm"))
    monkeypatch.setattr(
        "core.ultron.speak",
        lambda *_args, **_kwargs: calls.append("tts"),
    )

    dispatcher.dispatch_once()

    assert calls == []


def test_runtime_dispatcher_uses_existing_consumer_and_presenter():
    import core.ultron as ultron

    assert ultron._PROACTIVE_DISPATCHER._consumer is ultron._PROACTIVE_CONSUMER
    assert ultron._PROACTIVE_DISPATCHER._presenter is ultron._PROACTIVE_PRESENTER
    assert ultron._PROACTIVE_DISPATCHER._cooldown is ultron._PROACTIVE_COOLDOWN
    assert ultron._PROACTIVE_DISPATCHER._relevance is ultron._PROACTIVE_RELEVANCE
    assert ultron._PROACTIVE_DISPATCHER._policy is ultron._PROACTIVE_POLICY
    assert ultron._PROACTIVE_DISPATCHER._reasoner is ultron._PROACTIVE_REASONER


def test_reasoner_approval_allows_speech_and_records_cooldown():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event())
    dispatcher = ProactiveDispatcher(
        dispatcher._consumer,
        dispatcher._presenter,
        cooldown=cooldown,
        reasoner=ProactiveReasoner(),
    )

    result = dispatcher.dispatch_once_result()

    assert result.status == "presented"
    assert result.payload["message"] == "Code editor is active."
    assert cooldown.is_allowed() is False


def test_reasoner_silence_suppresses_speech_without_recording_cooldown():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)

    class Consumer:
        def consume_next(self):
            return {
                "message": "Code editor is active.",
                "application": "Code.exe",
                "window_title": "main.py",
            }

    class Presenter:
        def present(self, candidate):
            return candidate

    class SilentReasoner:
        def evaluate(self, candidate):
            return {
                "should_speak": False,
                "message": "",
                "reason": "trivial_change",
            }

    dispatcher = ProactiveDispatcher(
        Consumer(),
        Presenter(),
        cooldown=cooldown,
        reasoner=SilentReasoner(),
    )

    result = dispatcher.dispatch_once_result()

    assert result.status == "reasoner_rejected"
    assert result.payload is None
    assert cooldown.is_allowed() is True


def test_malformed_or_exception_reasoner_results_reject_safely():
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

    class MalformedReasoner:
        def evaluate(self, _candidate):
            return {"should_speak": "yes"}

    class BrokenReasoner:
        def evaluate(self, _candidate):
            raise TimeoutError()

    for reasoner in (MalformedReasoner(), BrokenReasoner()):
        result = ProactiveDispatcher(Consumer(), Presenter(), reasoner=reasoner).dispatch_once_result()
        assert result.status == "reasoner_rejected"


def test_reasoner_receives_only_bounded_three_field_candidate():
    captured = []
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
        def evaluate(self, value):
            captured.append(value)
            return {
                "should_speak": True,
                "message": "Code editor is active.",
                "reason": "approved",
            }

    result = ProactiveDispatcher(Consumer(), Presenter(), reasoner=Reasoner()).dispatch_once_result()

    assert result.status == "presented"
    assert captured == [candidate]
    assert set(captured[0]) == {"message", "application", "window_title"}


def test_policy_acceptance_presents_and_records_cooldown():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event())
    dispatcher = ProactiveDispatcher(
        dispatcher._consumer,
        dispatcher._presenter,
        cooldown=cooldown,
        policy=ProactivePolicy(),
    )

    result = dispatcher.dispatch_once_result()

    assert result.status == "presented"
    assert cooldown.is_allowed() is False


def test_policy_rejection_returns_rejected_without_recording_cooldown():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event())
    dispatcher = ProactiveDispatcher(
        dispatcher._consumer,
        dispatcher._presenter,
        cooldown=cooldown,
        policy=ProactivePolicy(),
    )
    first = dispatcher.dispatch_once_result()
    queue.push(_event())

    second = dispatcher.dispatch_once_result()

    assert first.status == "presented"
    assert second.status == "cooldown"

    cooldown.reset()
    queue.push(_event())
    rejected = dispatcher.dispatch_once_result()
    assert rejected.status == "rejected"
    assert cooldown.is_allowed() is True


def test_policy_is_not_called_when_presenter_rejects_or_raises():
    calls = []
    candidate = {
        "event": "desktop_changed",
        "message": "switch",
        "application": "Code.exe",
        "window_title": "main.py",
    }

    class Consumer:
        def consume_next(self):
            return candidate

    class Presenter:
        def __init__(self, error=False):
            self.error = error

        def present(self, _candidate):
            if self.error:
                raise RuntimeError("presenter failure")
            return None

    class Policy:
        def allow(self, _payload):
            calls.append(True)
            return True

    for presenter in (Presenter(), Presenter(error=True)):
        assert ProactiveDispatcher(Consumer(), presenter, policy=Policy()).dispatch_once_result().status == "rejected"

    assert calls == []


def test_policy_rejection_does_not_call_presenter():
    calls = []

    class Consumer:
        def consume_next(self):
            return {
                "event": "desktop_changed",
                "message": "switch",
                "application": "Code.exe",
                "window_title": "main.py",
            }

    class Presenter:
        def present(self, _candidate):
            calls.append(True)
            return {
                "message": "switch",
                "application": "Code.exe",
                "window_title": "main.py",
            }

    class Policy:
        def allow(self, _payload):
            return False

    result = ProactiveDispatcher(Consumer(), Presenter(), policy=Policy()).dispatch_once_result()

    assert result.status == "rejected"
    assert calls == [True]


def test_irrelevant_candidate_is_consumed_once_and_not_presented():
    calls = []

    class Consumer:
        def __init__(self):
            self.count = 0

        def consume_next(self):
            self.count += 1
            return _candidate(application="explorer.exe")

    class Presenter:
        def present(self, _candidate):
            calls.append(True)
            return {"message": "unexpected"}

    consumer = Consumer()
    dispatcher = ProactiveDispatcher(
        consumer,
        Presenter(),
        relevance=ProactiveRelevance(),
    )

    assert dispatcher.dispatch_once() is None
    assert consumer.count == 1
    assert calls == []


def test_irrelevant_candidate_does_not_record_cooldown():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)

    class Consumer:
        def consume_next(self):
            return _candidate(application="explorer.exe")

    class Presenter:
        def present(self, _candidate):
            raise AssertionError("presenter must not be called")

    dispatcher = ProactiveDispatcher(
        Consumer(),
        Presenter(),
        cooldown=cooldown,
        relevance=ProactiveRelevance(),
    )

    assert dispatcher.dispatch_once() is None
    assert cooldown.is_allowed() is True


def test_dispatch_without_relevance_preserves_existing_behavior():
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event("explorer.exe"))

    assert dispatcher.dispatch_once() is not None


def test_dispatch_once_result_reports_presented():
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event())

    result = dispatcher.dispatch_once_result()

    assert result == ProactiveDispatchResult(
        "presented",
        {
            "message": "Code editor is active.",
            "application": "Code.exe",
            "window_title": "main.py",
        },
    )


def test_dispatch_once_result_reports_no_candidate():
    dispatcher, _queue, guard = _dispatcher()
    guard.set_idle()

    assert dispatcher.dispatch_once_result().status == "no_candidate"


def test_dispatch_once_result_reports_cooldown_before_consumer():
    class BlockedCooldown:
        def is_allowed(self):
            return False

    class UnexpectedConsumer:
        def consume_next(self):
            raise AssertionError("consumer must not be called")

    result = ProactiveDispatcher(
        UnexpectedConsumer(),
        object(),
        cooldown=BlockedCooldown(),
    ).dispatch_once_result()

    assert result.status == "cooldown"


def test_dispatch_once_result_reports_irrelevant():
    class Consumer:
        def consume_next(self):
            return {
                "event": "desktop_changed",
                "message": "switch",
                "application": "explorer.exe",
                "window_title": "Desktop",
            }

    result = ProactiveDispatcher(
        Consumer(),
        object(),
        relevance=ProactiveRelevance(),
    ).dispatch_once_result()

    assert result.status == "irrelevant"


def test_dispatch_once_result_reports_rejected_presenter_and_exceptions():
    candidate = {
        "event": "desktop_changed",
        "message": "switch",
        "application": "Code.exe",
        "window_title": "main.py",
    }

    class Consumer:
        def consume_next(self):
            return candidate

    class RejectingPresenter:
        def present(self, _candidate):
            return None

    class BrokenPresenter:
        def present(self, _candidate):
            raise RuntimeError("private failure")

    for presenter in (RejectingPresenter(), BrokenPresenter()):
        result = ProactiveDispatcher(Consumer(), presenter).dispatch_once_result()
        assert result.status == "rejected"


def test_dispatch_once_result_reports_consumer_exception():
    class BrokenConsumer:
        def consume_next(self):
            raise RuntimeError("private failure")

    result = ProactiveDispatcher(BrokenConsumer(), object()).dispatch_once_result()

    assert result.status == "rejected"


def test_cooldown_blocks_before_consumer_access():
    calls = []

    class BlockedCooldown:
        def is_allowed(self):
            return False

    class UnexpectedConsumer:
        def consume_next(self):
            calls.append("consumer")
            return {"event": "desktop_changed"}

    class UnexpectedPresenter:
        def present(self, _candidate):
            calls.append("presenter")
            return {}

    dispatcher = ProactiveDispatcher(
        UnexpectedConsumer(),
        UnexpectedPresenter(),
        BlockedCooldown(),
    )

    assert dispatcher.dispatch_once() is None
    assert calls == []


def test_cooldown_block_preserves_queued_event():
    now = [0.0]
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    guard.set_idle()
    queue.push(_event())
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: now[0])
    cooldown.record()
    dispatcher = ProactiveDispatcher(
        ProactiveConsumer(queue, guard),
        ProactivePresenter(guard),
        cooldown,
    )

    assert dispatcher.dispatch_once() is None
    assert len(queue) == 1


def test_successful_presentation_records_cooldown():
    now = [0.0]
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: now[0])
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event())
    dispatcher = ProactiveDispatcher(
        dispatcher._consumer,
        dispatcher._presenter,
        cooldown,
    )

    assert dispatcher.dispatch_once() is not None
    assert cooldown.is_allowed() is False


def test_empty_queue_does_not_record_cooldown():
    now = [0.0]
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: now[0])
    dispatcher, _queue, guard = _dispatcher()
    guard.set_idle()
    dispatcher = ProactiveDispatcher(
        dispatcher._consumer,
        dispatcher._presenter,
        cooldown,
    )

    assert dispatcher.dispatch_once() is None
    assert cooldown.is_allowed() is True


def test_presenter_rejection_does_not_record_cooldown():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)

    class Consumer:
        def consume_next(self):
            return {"event": "desktop_changed"}

    class Presenter:
        def present(self, _candidate):
            return None

    assert ProactiveDispatcher(Consumer(), Presenter(), cooldown).dispatch_once() is None
    assert cooldown.is_allowed() is True


def test_presenter_exception_does_not_record_cooldown():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 0.0)

    class Consumer:
        def consume_next(self):
            return {"event": "desktop_changed"}

    class Presenter:
        def present(self, _candidate):
            raise RuntimeError("failed")

    assert ProactiveDispatcher(Consumer(), Presenter(), cooldown).dispatch_once() is None
    assert cooldown.is_allowed() is True


def test_cooldown_dispatch_still_processes_one_event():
    now = [0.0]
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: now[0])
    dispatcher, queue, guard = _dispatcher()
    guard.set_idle()
    queue.push(_event("first"))
    queue.push(_event("second"))
    dispatcher = ProactiveDispatcher(
        dispatcher._consumer,
        dispatcher._presenter,
        cooldown,
    )

    assert dispatcher.dispatch_once()["application"] == "first"
    assert len(queue) == 1
    assert dispatcher.dispatch_once() is None
    assert len(queue) == 1