import pytest

from core import ultron
from core.events import EventBus, EventType
from core.proactive_activity_guard import ProactiveActivityGuard
from core.proactive_consumer import ProactiveConsumer
from core.proactive_cooldown import ProactiveCooldown
from core.proactive_dispatcher import ProactiveDispatcher
from core.proactive_event_queue import ProactiveEventQueue
from core.proactive_policy import ProactivePolicy
from core.proactive_presenter import ProactivePresenter
from core.proactive_relevance import ProactiveRelevance
from core.proactive_speech import ProactiveSpeech


@pytest.fixture
def isolated_runtime(monkeypatch):
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    consumer = ProactiveConsumer(queue, guard)
    presenter = ProactivePresenter(guard)
    now = [100.0]
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: now[0])
    relevance = ProactiveRelevance()
    policy = ProactivePolicy()
    dispatcher = ProactiveDispatcher(
        consumer,
        presenter,
        cooldown,
        relevance,
        policy,
    )
    speech_calls = []

    def fake_tts(payload):
        speech_calls.append(payload)
        return True

    speech = ProactiveSpeech(fake_tts)
    event_bus = EventBus()
    queue.subscribe(event_bus)
    guard.subscribe(event_bus)

    monkeypatch.setattr(ultron, "EVENT_BUS", event_bus)
    monkeypatch.setattr(ultron, "_PROACTIVE_EVENT_QUEUE", queue)
    monkeypatch.setattr(ultron, "_PROACTIVE_ACTIVITY_GUARD", guard)
    monkeypatch.setattr(ultron, "_PROACTIVE_CONSUMER", consumer)
    monkeypatch.setattr(ultron, "_PROACTIVE_PRESENTER", presenter)
    monkeypatch.setattr(ultron, "_PROACTIVE_COOLDOWN", cooldown)
    monkeypatch.setattr(ultron, "_PROACTIVE_RELEVANCE", relevance)
    monkeypatch.setattr(ultron, "_PROACTIVE_POLICY", policy)
    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", dispatcher)
    monkeypatch.setattr(ultron, "_PROACTIVE_SPEECH", speech)

    yield {
        "bus": event_bus,
        "queue": queue,
        "guard": guard,
        "cooldown": cooldown,
        "speech_calls": speech_calls,
        "now": now,
    }

    queue.unsubscribe(event_bus)
    guard.unsubscribe(event_bus)


def _emit_change(event_bus):
    event_bus.emit(
        EventType.PROACTIVE_DESKTOP_EVENT,
        event="desktop_changed",
        reason="meaningful_change",
        application="notepad.exe",
        window_title="notes.txt - Notepad",
    )


def _expected_payload():
    return {
        "message": "notepad.exe is active.",
        "application": "notepad.exe",
        "window_title": "notes.txt - Notepad",
    }


def test_synthetic_event_reaches_speech_end_to_end(isolated_runtime):
    runtime = isolated_runtime
    runtime["guard"].set_idle()

    _emit_change(runtime["bus"])

    assert len(runtime["queue"]) == 1
    result = ultron.trigger_proactive()

    assert result == _expected_payload()
    assert runtime["speech_calls"] == ["notepad.exe is active."]
    assert len(runtime["queue"]) == 0


def test_blocked_activity_preserves_event_then_allowed_dispatches_once(
    isolated_runtime,
):
    runtime = isolated_runtime
    _emit_change(runtime["bus"])

    assert ultron.trigger_proactive() is None
    assert len(runtime["queue"]) == 1
    assert runtime["speech_calls"] == []

    runtime["guard"].set_idle()
    assert ultron.trigger_proactive() == _expected_payload()
    assert len(runtime["queue"]) == 0
    assert runtime["speech_calls"] == ["notepad.exe is active."]


def test_cooldown_blocks_second_end_to_end_dispatch(isolated_runtime):
    runtime = isolated_runtime
    runtime["guard"].set_idle()
    _emit_change(runtime["bus"])

    assert ultron.trigger_proactive() == _expected_payload()
    assert len(runtime["speech_calls"]) == 1

    _emit_change(runtime["bus"])
    assert len(runtime["queue"]) == 1
    assert ultron.trigger_proactive() is None
    assert len(runtime["queue"]) == 1
    assert len(runtime["speech_calls"]) == 1