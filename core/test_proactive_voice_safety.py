from types import SimpleNamespace

import pytest

from core import ultron
from core.events import EventBus, EventType
from core.proactive_activity_guard import (
    ProactiveActivityGuard,
    ProactiveActivityState,
)
from core.proactive_consumer import ProactiveConsumer
from core.proactive_cooldown import ProactiveCooldown
from core.proactive_dispatcher import ProactiveDispatcher
from core.proactive_engine import ProactiveEngine
from core.proactive_event_queue import ProactiveEventQueue
from core.proactive_policy import ProactivePolicy
from core.proactive_presenter import ProactivePresenter
from core.proactive_relevance import ProactiveRelevance
from core.proactive_speech import ProactiveSpeech
from core.desktop_context_tracker import DesktopContextTracker


def _context(application="Code.exe", title="main.py", process_id=1):
    return {
        "active_window": {
            "application": application,
            "window_title": title,
            "process_id": process_id,
        },
        "timestamp": f"{application}-{title}-{process_id}",
    }


@pytest.fixture
def runtime(monkeypatch):
    event_bus = EventBus()
    queue = ProactiveEventQueue()
    guard = ProactiveActivityGuard()
    queue.subscribe(event_bus)
    guard.subscribe(event_bus)
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 100.0)
    dispatcher = ProactiveDispatcher(
        ProactiveConsumer(queue, guard),
        ProactivePresenter(guard),
        cooldown,
        ProactiveRelevance(),
        ProactivePolicy(),
    )
    speech_calls = []
    speech = ProactiveSpeech(
        lambda message: speech_calls.append(message) or True
    )

    monkeypatch.setattr(ultron, "EVENT_BUS", event_bus)
    monkeypatch.setattr(ultron, "_DESKTOP_CONTEXT_TRACKER", DesktopContextTracker())
    monkeypatch.setattr(
        ultron,
        "_PROACTIVE_ENGINE",
        ProactiveEngine(cooldown_seconds=0.0),
    )
    monkeypatch.setattr(ultron, "_PROACTIVE_EVENT_QUEUE", queue)
    monkeypatch.setattr(ultron, "_PROACTIVE_ACTIVITY_GUARD", guard)
    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", dispatcher)
    monkeypatch.setattr(ultron, "_PROACTIVE_SPEECH", speech)

    def fake_chat(**_kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(
                content="normal response",
                role="assistant",
                tool_calls=[],
            )
        )

    monkeypatch.setattr(ultron, "chat", fake_chat)
    yield {
        "bus": event_bus,
        "queue": queue,
        "guard": guard,
        "speech_calls": speech_calls,
    }
    queue.unsubscribe(event_bus)
    guard.unsubscribe(event_bus)


def _run_eligible_request(monkeypatch):
    contexts = iter([
        _context(),
        _context("PowerShell.exe", "PowerShell", 2),
    ])
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: next(contexts))
    messages = [{"role": "system", "content": "base"}]
    ultron.run_agent("first", messages)
    return ultron.run_agent("second", messages)


@pytest.mark.parametrize(
    "state_setter",
    [
        "set_user_active",
        "set_listening",
        "set_transcribing",
        "set_thinking",
        "set_speaking",
        "set_barge_in",
    ],
    ids=[
        "USER_ACTIVE",
        "LISTENING",
        "TRANSCRIBING",
        "THINKING",
        "SPEAKING",
        "INTERRUPTED",
    ],
)
def test_blocked_voice_state_preserves_event_and_prevents_speech(
    monkeypatch,
    runtime,
    state_setter,
):
    getattr(runtime["guard"], state_setter)()

    assert _run_eligible_request(monkeypatch) == "normal response"
    assert len(runtime["queue"]) == 1
    assert runtime["speech_calls"] == []

    runtime["guard"].set_idle()
    assert ultron.trigger_proactive() == {
        "message": "Terminal is active.",
        "application": "PowerShell.exe",
        "window_title": "PowerShell",
    }
    assert len(runtime["queue"]) == 0
    assert runtime["speech_calls"] == ["Terminal is active."]


def test_voice_lifecycle_events_protect_until_session_ends():
    event_bus = EventBus()
    guard = ProactiveActivityGuard()
    guard.subscribe(event_bus)

    event_bus.emit(EventType.WAKE_DETECTED)
    assert guard.state is ProactiveActivityState.USER_ACTIVE
    assert guard.is_allowed() is False

    event_bus.emit(EventType.LISTENING_STARTED)
    assert guard.state is ProactiveActivityState.LISTENING
    event_bus.emit(EventType.TRANSCRIPTION_READY, characters=4)
    assert guard.state is ProactiveActivityState.TRANSCRIBING
    event_bus.emit(EventType.THINKING_STARTED)
    assert guard.state is ProactiveActivityState.THINKING
    event_bus.emit(EventType.SPEAKING_STARTED)
    assert guard.state is ProactiveActivityState.SPEAKING
    event_bus.emit(EventType.SPEAKING_COMPLETED, interrupted=False)
    assert guard.state is ProactiveActivityState.USER_ACTIVE
    event_bus.emit(EventType.BARGE_IN)
    assert guard.state is ProactiveActivityState.INTERRUPTED
    assert guard.is_allowed() is False

    event_bus.emit(EventType.SESSION_ENDED)
    assert guard.state is ProactiveActivityState.IDLE
    assert guard.is_allowed() is True
    guard.unsubscribe(event_bus)


def test_interrupted_speaking_completion_remains_blocked():
    event_bus = EventBus()
    guard = ProactiveActivityGuard()
    guard.subscribe(event_bus)

    event_bus.emit(EventType.SPEAKING_STARTED)
    event_bus.emit(EventType.SPEAKING_COMPLETED, interrupted=True)

    assert guard.state is ProactiveActivityState.INTERRUPTED
    assert guard.is_allowed() is False
    guard.unsubscribe(event_bus)