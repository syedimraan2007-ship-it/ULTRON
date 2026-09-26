from copy import deepcopy

from core.proactive_speech import ProactiveSpeech


def _payload(**overrides):
    payload = {
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    payload.update(overrides)
    return payload


def test_valid_payload_calls_tts_once():
    calls = []
    speech = ProactiveSpeech(lambda message: calls.append(message) or True)

    result = speech.speak(_payload())

    assert result is True
    assert calls == ["You switched to Code.exe."]


def test_invalid_payload_does_not_call_tts():
    calls = []
    speech = ProactiveSpeech(lambda message: calls.append(message) or True)

    assert speech.speak(None) is False
    assert calls == []


def test_missing_required_fields_are_rejected():
    calls = []
    speech = ProactiveSpeech(lambda message: calls.append(message) or True)

    for field in ("message", "application", "window_title"):
        payload = _payload()
        payload.pop(field)
        assert speech.speak(payload) is False

    assert calls == []


def test_oversized_fields_are_rejected():
    calls = []
    speech = ProactiveSpeech(lambda message: calls.append(message) or True)

    assert speech.speak(_payload(message="x" * 513)) is False
    assert speech.speak(_payload(application="x" * 257)) is False
    assert speech.speak(_payload(window_title="x" * 257)) is False
    assert calls == []


def test_wrong_field_types_are_rejected():
    calls = []
    speech = ProactiveSpeech(lambda message: calls.append(message) or True)

    assert speech.speak(_payload(message=1)) is False
    assert speech.speak(_payload(application=[])) is False
    assert speech.speak(_payload(window_title=None)) is False
    assert calls == []


def test_tts_false_result_is_normalized_to_false():
    calls = []
    speech = ProactiveSpeech(lambda message: calls.append(message) or False)

    assert speech.speak(_payload()) is False
    assert len(calls) == 1


def test_tts_exception_returns_false_without_exposing_details():
    calls = []

    def failing_tts(_message):
        calls.append(True)
        raise RuntimeError("secret implementation detail")

    speech = ProactiveSpeech(failing_tts)

    assert speech.speak(_payload()) is False
    assert calls == [True]


def test_payload_remains_unchanged():
    speech = ProactiveSpeech(lambda _message: True)
    payload = _payload()
    before = deepcopy(payload)

    speech.speak(payload)

    assert payload == before


def test_adapter_has_no_queue_dispatch_policy_or_event_bus_surface():
    speech = ProactiveSpeech(lambda _message: True)

    assert not hasattr(speech, "consume_next")
    assert not hasattr(speech, "dispatch_once")
    assert not hasattr(speech, "allow")
    assert not hasattr(speech, "subscribe")
    assert not hasattr(speech, "poll")
    assert not hasattr(speech, "start")


def test_runtime_creates_one_explicit_speech_adapter():
    import core.ultron as ultron

    assert isinstance(ultron._PROACTIVE_SPEECH, ProactiveSpeech)