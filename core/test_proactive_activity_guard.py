from core.proactive_activity_guard import (
    ProactiveActivityGuard,
    ProactiveActivityState,
)


def test_fresh_guard_is_conservatively_blocked():
    guard = ProactiveActivityGuard()

    assert guard.state is ProactiveActivityState.UNKNOWN
    assert guard.is_allowed() is False


def test_idle_state_is_allowed():
    guard = ProactiveActivityGuard()

    guard.set_idle()

    assert guard.state is ProactiveActivityState.IDLE
    assert guard.is_allowed() is True


def test_listening_blocks_proactive_output():
    guard = ProactiveActivityGuard()
    guard.set_listening()

    assert guard.state is ProactiveActivityState.LISTENING
    assert guard.is_allowed() is False


def test_thinking_blocks_proactive_output():
    guard = ProactiveActivityGuard()
    guard.set_thinking()

    assert guard.state is ProactiveActivityState.THINKING
    assert guard.is_allowed() is False


def test_speaking_blocks_proactive_output():
    guard = ProactiveActivityGuard()
    guard.set_speaking()

    assert guard.state is ProactiveActivityState.SPEAKING
    assert guard.is_allowed() is False


def test_barge_in_blocks_proactive_output():
    guard = ProactiveActivityGuard()
    guard.set_barge_in()

    assert guard.state is ProactiveActivityState.INTERRUPTED
    assert guard.is_allowed() is False


def test_returning_to_idle_allows_output():
    guard = ProactiveActivityGuard()
    guard.set_thinking()
    guard.set_idle()

    assert guard.is_allowed() is True


def test_state_transitions_are_deterministic():
    guard = ProactiveActivityGuard()

    transitions = [
        (guard.set_user_active, ProactiveActivityState.USER_ACTIVE),
        (guard.set_listening, ProactiveActivityState.LISTENING),
        (guard.set_transcribing, ProactiveActivityState.TRANSCRIBING),
        (guard.set_thinking, ProactiveActivityState.THINKING),
        (guard.set_speaking, ProactiveActivityState.SPEAKING),
        (guard.set_barge_in, ProactiveActivityState.INTERRUPTED),
        (guard.set_idle, ProactiveActivityState.IDLE),
    ]

    for transition, expected_state in transitions:
        transition()
        assert guard.state is expected_state
        assert guard.is_allowed() is (expected_state is ProactiveActivityState.IDLE)


def test_guard_state_is_instance_local():
    first = ProactiveActivityGuard()
    second = ProactiveActivityGuard()
    first.set_idle()

    assert first.is_allowed() is True
    assert second.state is ProactiveActivityState.UNKNOWN
    assert second.is_allowed() is False


def test_repeated_state_updates_are_idempotent():
    guard = ProactiveActivityGuard()
    guard.set_idle()
    first_state = guard.state
    guard.set_idle()
    second_state = guard.state

    assert first_state is second_state is ProactiveActivityState.IDLE
    assert guard.is_allowed() is True


def test_guard_does_not_consume_or_invoke_any_external_system():
    guard = ProactiveActivityGuard()

    guard.set_idle()

    assert guard.is_allowed() is True