from core.events import Event, EventType
from core.proactive_activity_guard import ProactiveActivityGuard
from core.proactive_consumer import ProactiveConsumer
from core.proactive_event_queue import ProactiveEventQueue


def _event(**overrides):
    data = {
        "event": "desktop_changed",
        "reason": "meaningful_change",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    data.update(overrides)
    return Event(EventType.PROACTIVE_DESKTOP_EVENT, data)


def test_empty_queue_returns_none():
    consumer = ProactiveConsumer(ProactiveEventQueue())

    assert consumer.consume_next() is None


def test_valid_event_returns_deterministic_candidate():
    queue = ProactiveEventQueue()
    queue.push(_event(application="Visual Studio Code", window_title="ultron.py"))

    candidate = ProactiveConsumer(queue).consume_next()

    assert candidate == {
        "event": "desktop_changed",
        "message": "Code editor is active.",
        "application": "Visual Studio Code",
        "window_title": "ultron.py",
    }


def test_fifo_consumption():
    queue = ProactiveEventQueue()
    queue.push(_event(application="first"))
    queue.push(_event(application="second"))
    consumer = ProactiveConsumer(queue)

    assert consumer.consume_next()["application"] == "first"
    assert consumer.consume_next()["application"] == "second"


def test_successful_consumption_removes_event():
    queue = ProactiveEventQueue()
    queue.push(_event())
    consumer = ProactiveConsumer(queue)

    assert consumer.consume_next() is not None
    assert len(queue) == 0


def test_malformed_event_is_rejected_and_not_removed():
    queue = ProactiveEventQueue()
    queue._events.append({
        "event": "not_desktop_changed",
        "reason": "bad",
        "application": "Code.exe",
        "window_title": "main.py",
    })
    consumer = ProactiveConsumer(queue)

    assert consumer.consume_next() is None
    assert len(queue) == 1


def test_process_id_is_never_included():
    queue = ProactiveEventQueue()
    queue.push(_event(process_id="1234"))
    candidate = ProactiveConsumer(queue).consume_next()

    assert candidate is not None
    assert "process_id" not in candidate
    assert "1234" not in str(candidate)


def test_oversized_metadata_and_message_are_bounded():
    queue = ProactiveEventQueue()
    oversized = "A" * 1000
    queue._events.append({
        "event": "desktop_changed",
        "reason": oversized,
        "application": oversized,
        "window_title": oversized,
    })

    candidate = ProactiveConsumer(queue).consume_next()

    assert candidate is not None
    assert len(candidate["application"]) == 256
    assert len(candidate["window_title"]) == 256
    assert len(candidate["message"]) <= 512


def test_consumer_does_not_call_llm_or_tts(monkeypatch):
    calls = []
    queue = ProactiveEventQueue()
    queue.push(_event())

    monkeypatch.setattr(
        "core.ultron.chat",
        lambda **_kwargs: calls.append("llm"),
    )
    monkeypatch.setattr(
        "core.ultron.speak",
        lambda *_args, **_kwargs: calls.append("tts"),
    )

    ProactiveConsumer(queue).consume_next()

    assert calls == []


def test_queue_unchanged_when_no_valid_event_is_available():
    queue = ProactiveEventQueue()
    queue._events.append({"event": "desktop_changed"})
    consumer = ProactiveConsumer(queue)

    assert consumer.consume_next() is None
    assert queue.peek() == {"event": "desktop_changed"}


def test_multiple_events_are_consumed_one_at_a_time():
    queue = ProactiveEventQueue()
    queue.push(_event(application="first"))
    queue.push(_event(application="second"))
    queue.push(_event(application="third"))
    consumer = ProactiveConsumer(queue)

    assert len(queue) == 3
    assert consumer.consume_next()["application"] == "first"
    assert len(queue) == 2
    assert consumer.consume_next()["application"] == "second"
    assert len(queue) == 1
    assert consumer.consume_next()["application"] == "third"
    assert len(queue) == 0


def test_blocked_guard_leaves_event_queued():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    queue.push(_event())

    assert ProactiveConsumer(queue, guard).consume_next() is None
    assert len(queue) == 1
    assert queue.peek()["application"] == "Code.exe"


def test_idle_guard_consumes_valid_event():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    guard.set_idle()
    queue.push(_event())

    candidate = ProactiveConsumer(queue, guard).consume_next()

    assert candidate is not None
    assert len(queue) == 0


def test_blocked_to_idle_transition_allows_consumption():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    consumer = ProactiveConsumer(queue, guard)
    queue.push(_event())

    assert consumer.consume_next() is None
    guard.set_idle()
    assert consumer.consume_next() is not None
    assert len(queue) == 0


def test_malformed_event_stays_queued_when_idle():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    guard.set_idle()
    queue._events.append({"event": "invalid"})

    assert ProactiveConsumer(queue, guard).consume_next() is None
    assert len(queue) == 1


def test_fifo_order_remains_intact_with_activity_guard():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    guard.set_idle()
    queue.push(_event(application="first"))
    queue.push(_event(application="second"))

    consumer = ProactiveConsumer(queue, guard)
    assert consumer.consume_next()["application"] == "first"
    assert consumer.consume_next()["application"] == "second"


def test_runtime_consumer_uses_existing_queue_and_guard():
    import core.ultron as ultron

    assert ultron._PROACTIVE_CONSUMER._queue is ultron._PROACTIVE_EVENT_QUEUE
    assert (
        ultron._PROACTIVE_CONSUMER._activity_guard
        is ultron._PROACTIVE_ACTIVITY_GUARD
    )


def test_idle_transition_does_not_automatically_consume_event():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    consumer = ProactiveConsumer(queue, guard)
    queue.push(_event())

    guard.set_idle()

    assert len(queue) == 1
    assert consumer.consume_next() is not None


def test_consumer_behavior_remains_independent_of_reasoning():
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    guard.set_idle()
    queue.push(_event())
    consumer = ProactiveConsumer(queue, guard)

    candidate = consumer.consume_next()

    assert candidate is not None
    assert candidate["message"] == "Code editor is active."
    assert len(queue) == 0