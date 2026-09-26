from copy import deepcopy

from core import ultron


def _install_voice_fakes(monkeypatch, inputs, speech_results=None):
    input_values = iter(inputs)
    speech_values = iter(speech_results or [])
    agent_calls = []
    events = []

    monkeypatch.setattr(ultron, "listen", lambda: next(input_values))

    def fake_run_agent(user_input, messages):
        agent_calls.append(
            {
                "input": user_input,
                "messages": deepcopy(messages),
            }
        )
        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": f"response to: {user_input}",
            }
        )
        return f"response to: {user_input}"

    monkeypatch.setattr(ultron, "run_agent", fake_run_agent)
    monkeypatch.setattr(
        ultron,
        "_speak_once",
        lambda answer: next(speech_values, False),
    )
    monkeypatch.setattr(
        ultron.EVENT_BUS,
        "emit",
        lambda event_type, **data: events.append((event_type, data)),
    )

    return agent_calls, events


def _event_types(events):
    return [event_type for event_type, _ in events]


def _voice_events(events):
    relevant_events = {
        ultron.EventType.LISTENING_STARTED,
        ultron.EventType.THINKING_STARTED,
        ultron.EventType.SPEAKING_STARTED,
        ultron.EventType.SPEAKING_COMPLETED,
        ultron.EventType.BARGE_IN,
    }

    return [
        event_type
        for event_type in _event_types(events)
        if event_type in relevant_events
    ]


def test_continuous_session_preserves_three_turn_conversation_history(monkeypatch):
    messages = [{"role": "system", "content": "system"}]
    agent_calls, events = _install_voice_fakes(
        monkeypatch,
        [
            "Hello Ultron",
            "What did I just say?",
            "And what was my first question?",
            "",
        ],
    )

    state_machine = ultron.VoiceSessionStateMachine()
    ultron.voice_session(messages, state_machine, continuous=True)

    assert [call["input"] for call in agent_calls] == [
        "Hello Ultron",
        "What did I just say?",
        "And what was my first question?",
    ]
    assert agent_calls[0]["messages"] == [
        {"role": "system", "content": "system"},
    ]
    assert agent_calls[1]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Hello Ultron"},
        {"role": "assistant", "content": "response to: Hello Ultron"},
    ]
    assert agent_calls[2]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "Hello Ultron"},
        {"role": "assistant", "content": "response to: Hello Ultron"},
        {"role": "user", "content": "What did I just say?"},
        {
            "role": "assistant",
            "content": "response to: What did I just say?",
        },
    ]
    assert messages[-2:] == [
        {"role": "user", "content": "And what was my first question?"},
        {
            "role": "assistant",
            "content": "response to: And what was my first question?",
        },
    ]
    assert state_machine.state is ultron.VoiceSessionState.IDLE
    assert _voice_events(events).count(ultron.EventType.LISTENING_STARTED) == 4


def test_normal_turn_emits_listening_thinking_speaking_listening(monkeypatch):
    agent_calls, events = _install_voice_fakes(
        monkeypatch,
        ["first request", ""],
    )

    state_machine = ultron.VoiceSessionStateMachine()
    ultron.voice_session([], state_machine, continuous=True)

    assert agent_calls[0]["input"] == "first request"
    assert _voice_events(events)[:5] == [
        ultron.EventType.LISTENING_STARTED,
        ultron.EventType.THINKING_STARTED,
        ultron.EventType.SPEAKING_STARTED,
        ultron.EventType.SPEAKING_COMPLETED,
        ultron.EventType.LISTENING_STARTED,
    ]
    assert state_machine.state is ultron.VoiceSessionState.IDLE


def test_barge_in_returns_to_listening_without_duplicate_assistant_turn(
    monkeypatch,
):
    messages = [{"role": "system", "content": "system"}]
    agent_calls, events = _install_voice_fakes(
        monkeypatch,
        ["first request", "interruption", ""],
        speech_results=[True, False],
    )

    state_machine = ultron.VoiceSessionStateMachine()
    ultron.voice_session(messages, state_machine, continuous=True)

    assert [call["input"] for call in agent_calls] == [
        "first request",
        "interruption",
    ]
    assert agent_calls[1]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "first request"},
        {"role": "assistant", "content": "response to: first request"},
    ]
    assistant_messages = [
        message
        for message in messages
        if message["role"] == "assistant"
    ]
    assert assistant_messages == [
        {"role": "assistant", "content": "response to: first request"},
        {"role": "assistant", "content": "response to: interruption"},
    ]
    event_types = _voice_events(events)
    speaking_index = event_types.index(ultron.EventType.SPEAKING_STARTED)
    assert event_types[speaking_index:speaking_index + 5] == [
        ultron.EventType.SPEAKING_STARTED,
        ultron.EventType.SPEAKING_COMPLETED,
        ultron.EventType.BARGE_IN,
        ultron.EventType.LISTENING_STARTED,
        ultron.EventType.THINKING_STARTED,
    ]
    assert state_machine.state is ultron.VoiceSessionState.IDLE


def test_continuous_session_can_restart_after_silence_without_losing_history(
    monkeypatch,
):
    messages = [{"role": "system", "content": "system"}]
    agent_calls, events = _install_voice_fakes(
        monkeypatch,
        ["first request", "", "second request", ""],
    )

    state_machine = ultron.VoiceSessionStateMachine()
    ultron.voice_session(messages, state_machine, continuous=True)
    assert state_machine.state is ultron.VoiceSessionState.IDLE

    ultron.voice_session(messages, state_machine, continuous=True)

    assert agent_calls[1]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "first request"},
        {"role": "assistant", "content": "response to: first request"},
    ]
    assert state_machine.state is ultron.VoiceSessionState.IDLE


def test_wake_mode_emits_wake_event_and_stops_after_one_turn(monkeypatch):
    agent_calls, events = _install_voice_fakes(
        monkeypatch,
        ["wake-gated request", "unexpected second request"],
    )

    state_machine = ultron.VoiceSessionStateMachine()
    ultron.voice_session([], state_machine, continuous=False)

    assert [call["input"] for call in agent_calls] == ["wake-gated request"]
    assert ultron.EventType.WAKE_DETECTED in _event_types(events)
    assert state_machine.state is ultron.VoiceSessionState.IDLE
