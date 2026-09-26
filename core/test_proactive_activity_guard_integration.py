from core.events import EventBus, EventType
from core.proactive_activity_guard import (
    ProactiveActivityGuard,
    ProactiveActivityState,
)


def _guard_and_bus():
    event_bus = EventBus()
    guard = ProactiveActivityGuard()
    guard.subscribe(event_bus)
    return guard, event_bus


def test_fresh_runtime_guard_is_blocked():
    guard, _event_bus = _guard_and_bus()

    assert guard.state is ProactiveActivityState.UNKNOWN
    assert guard.is_allowed() is False


def test_session_ended_allows_proactive_output():
    guard, event_bus = _guard_and_bus()

    event_bus.emit(EventType.SESSION_ENDED)

    assert guard.state is ProactiveActivityState.IDLE
    assert guard.is_allowed() is True


def test_listening_event_blocks_output():
    guard, event_bus = _guard_and_bus()
    event_bus.emit(EventType.SESSION_ENDED)

    event_bus.emit(EventType.LISTENING_STARTED)

    assert guard.state is ProactiveActivityState.LISTENING
    assert guard.is_allowed() is False


def test_transcription_event_blocks_output():
    guard, event_bus = _guard_and_bus()
    event_bus.emit(EventType.TRANSCRIPTION_READY, characters=4)

    assert guard.state is ProactiveActivityState.TRANSCRIBING
    assert guard.is_allowed() is False


def test_thinking_event_blocks_output():
    guard, event_bus = _guard_and_bus()
    event_bus.emit(EventType.THINKING_STARTED)

    assert guard.state is ProactiveActivityState.THINKING
    assert guard.is_allowed() is False


def test_speaking_event_blocks_output():
    guard, event_bus = _guard_and_bus()
    event_bus.emit(EventType.SPEAKING_STARTED)

    assert guard.state is ProactiveActivityState.SPEAKING
    assert guard.is_allowed() is False


def test_barge_in_event_blocks_output():
    guard, event_bus = _guard_and_bus()
    event_bus.emit(EventType.BARGE_IN)

    assert guard.state is ProactiveActivityState.INTERRUPTED
    assert guard.is_allowed() is False


def test_speaking_completed_waits_for_post_speaking_event():
    guard, event_bus = _guard_and_bus()
    event_bus.emit(EventType.SPEAKING_STARTED)
    event_bus.emit(EventType.SPEAKING_COMPLETED, interrupted=False)

    assert guard.state is ProactiveActivityState.USER_ACTIVE
    assert guard.is_allowed() is False

    event_bus.emit(EventType.SESSION_ENDED)
    assert guard.is_allowed() is True


def test_interrupted_speaking_completion_maps_to_barge_in():
    guard, event_bus = _guard_and_bus()

    event_bus.emit(EventType.SPEAKING_COMPLETED, interrupted=True)

    assert guard.state is ProactiveActivityState.INTERRUPTED
    assert guard.is_allowed() is False


def test_unknown_or_malformed_events_are_ignored():
    guard, event_bus = _guard_and_bus()
    event_bus.emit(EventType.SESSION_ENDED)

    guard._handle_event(None)
    guard._handle_event(object())
    event_bus.emit(EventType.PROACTIVE_DESKTOP_EVENT, unexpected=True)

    assert guard.state is ProactiveActivityState.IDLE
    assert guard.is_allowed() is True


def test_duplicate_subscription_does_not_duplicate_handlers():
    guard, event_bus = _guard_and_bus()
    guard.subscribe(event_bus)

    assert len(event_bus._subscribers[EventType.SESSION_ENDED]) == 1
    event_bus.emit(EventType.SESSION_ENDED)
    assert guard.is_allowed() is True


def test_guard_state_persists_across_events():
    guard, event_bus = _guard_and_bus()

    event_bus.emit(EventType.SESSION_ENDED)
    event_bus.emit(EventType.LISTENING_STARTED)
    event_bus.emit(EventType.THINKING_STARTED)
    event_bus.emit(EventType.SPEAKING_STARTED)

    assert guard.state is ProactiveActivityState.SPEAKING
    assert guard.is_allowed() is False


def test_guard_instances_are_isolated():
    first, first_bus = _guard_and_bus()
    second, second_bus = _guard_and_bus()
    first_bus.emit(EventType.SESSION_ENDED)

    assert first.is_allowed() is True
    assert second.state is ProactiveActivityState.UNKNOWN
    assert second.is_allowed() is False
    second_bus.emit(EventType.SESSION_ENDED)
    assert second.is_allowed() is True