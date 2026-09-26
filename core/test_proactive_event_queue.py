from core.events import Event, EventBus, EventType
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


def test_valid_proactive_event_is_recorded():
    queue = ProactiveEventQueue()

    queue.push(_event())

    assert queue.pop() == {
        "event": "desktop_changed",
        "reason": "meaningful_change",
        "application": "Code.exe",
        "window_title": "main.py",
    }


def test_queue_preserves_fifo_order():
    queue = ProactiveEventQueue()
    queue.push(_event(application="first"))
    queue.push(_event(application="second"))

    assert queue.pop()["application"] == "first"
    assert queue.pop()["application"] == "second"


def test_empty_queue_and_clear_are_safe():
    queue = ProactiveEventQueue()

    assert queue.pop() is None
    assert queue.peek() is None
    queue.push(_event())
    queue.clear()
    assert len(queue) == 0
    assert queue.pop() is None


def test_capacity_discards_oldest_event():
    queue = ProactiveEventQueue(capacity=2)
    queue.push(_event(application="first"))
    queue.push(_event(application="second"))
    queue.push(_event(application="third"))

    assert len(queue) == 2
    assert queue.pop()["application"] == "second"
    assert queue.pop()["application"] == "third"


def test_oversized_strings_are_bounded():
    queue = ProactiveEventQueue()
    oversized = "x" * (queue.MAX_TEXT_LENGTH + 20)

    queue.push(
        _event(
            reason=oversized,
            application=oversized,
            window_title=oversized,
        )
    )

    result = queue.pop()
    assert result is not None
    assert len(result["reason"]) == queue.MAX_TEXT_LENGTH
    assert len(result["application"]) == queue.MAX_TEXT_LENGTH
    assert len(result["window_title"]) == queue.MAX_TEXT_LENGTH


def test_malformed_event_is_rejected():
    queue = ProactiveEventQueue()

    queue.push(_event(window_title=None))
    queue.push(Event(EventType.PROACTIVE_DESKTOP_EVENT, {"event": "wrong"}))

    assert len(queue) == 0


def test_non_proactive_event_is_rejected():
    queue = ProactiveEventQueue()

    queue.push(Event(EventType.ERROR, {"event": "desktop_changed"}))

    assert len(queue) == 0


def test_subscriber_receives_existing_proactive_event():
    event_bus = EventBus()
    queue = ProactiveEventQueue()
    queue.subscribe(event_bus)

    event_bus.emit(
        EventType.PROACTIVE_DESKTOP_EVENT,
        event="desktop_changed",
        reason="meaningful_change",
        application="Code.exe",
        window_title="main.py",
    )

    assert len(queue) == 1
    assert queue.peek()["application"] == "Code.exe"


def test_duplicate_subscription_does_not_duplicate_events():
    event_bus = EventBus()
    queue = ProactiveEventQueue()
    queue.subscribe(event_bus)
    queue.subscribe(event_bus)

    event_bus.emit(
        EventType.PROACTIVE_DESKTOP_EVENT,
        event="desktop_changed",
        reason="meaningful_change",
        application="Code.exe",
        window_title="main.py",
    )

    assert len(queue) == 1


def test_queue_state_is_instance_local():
    first = ProactiveEventQueue()
    second = ProactiveEventQueue()
    first.push(_event())

    assert len(first) == 1
    assert len(second) == 0


def test_runtime_queue_is_registered_once_and_receives_events():
    import core.ultron as ultron

    ultron._PROACTIVE_EVENT_QUEUE.clear()
    ultron.EVENT_BUS.emit(
        EventType.PROACTIVE_DESKTOP_EVENT,
        event="desktop_changed",
        reason="meaningful_change",
        application="Code.exe",
        window_title="main.py",
    )

    assert len(ultron._PROACTIVE_EVENT_QUEUE) == 1
    ultron._PROACTIVE_EVENT_QUEUE.clear()


def test_subscriber_failure_does_not_break_run_agent(monkeypatch):
    import core.ultron as ultron

    calls = []
    monkeypatch.setattr(
        ultron,
        "get_desktop_context",
        lambda: {
            "active_window": {
                "application": "Code.exe",
                "window_title": "main.py",
                "process_id": 1,
            }
        },
    )
    monkeypatch.setattr(ultron, "chat", lambda **kwargs: calls.append(kwargs) or type(
        "Response",
        (),
        {"message": type("Message", (), {"content": "response", "tool_calls": []})()},
    )())
    monkeypatch.setattr(
        ultron._PROACTIVE_EVENT_QUEUE,
        "push",
        lambda _event: (_ for _ in ()).throw(RuntimeError("queue unavailable")),
    )

    result = ultron.run_agent("request", [{"role": "system", "content": "base"}])

    assert result == "response"
    assert len(calls) == 1