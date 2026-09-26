from copy import deepcopy

from core import ultron
from core.proactive_dispatch_result import ProactiveDispatchResult


def _payload():
    return {
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }


def test_presented_result_calls_speech_once_and_returns_payload(monkeypatch):
    payload = _payload()
    calls = []
    monkeypatch.setattr(
        ultron._PROACTIVE_DISPATCHER,
        "dispatch_once_result",
        lambda: ProactiveDispatchResult("presented", payload),
    )
    monkeypatch.setattr(
        ultron._PROACTIVE_SPEECH,
        "speak",
        lambda value: calls.append(value) or True,
    )

    result = ultron.run_proactive_once()

    assert result == payload
    assert calls == [payload]


def test_non_presented_result_does_not_call_speech(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ultron._PROACTIVE_DISPATCHER,
        "dispatch_once_result",
        lambda: ProactiveDispatchResult("no_candidate"),
    )
    monkeypatch.setattr(
        ultron._PROACTIVE_SPEECH,
        "speak",
        lambda _payload: calls.append(True) or True,
    )

    assert ultron.run_proactive_once() is None
    assert calls == []


def test_speech_false_returns_none(monkeypatch):
    monkeypatch.setattr(
        ultron._PROACTIVE_DISPATCHER,
        "dispatch_once_result",
        lambda: ProactiveDispatchResult("presented", _payload()),
    )
    monkeypatch.setattr(ultron._PROACTIVE_SPEECH, "speak", lambda _payload: False)

    assert ultron.run_proactive_once() is None


def test_speech_exception_returns_none(monkeypatch):
    monkeypatch.setattr(
        ultron._PROACTIVE_DISPATCHER,
        "dispatch_once_result",
        lambda: ProactiveDispatchResult("presented", _payload()),
    )

    def fail(_payload):
        raise RuntimeError("private speech failure")

    monkeypatch.setattr(ultron._PROACTIVE_SPEECH, "speak", fail)

    assert ultron.run_proactive_once() is None


def test_dispatcher_exception_returns_none_and_skips_speech(monkeypatch):
    calls = []

    def fail():
        raise RuntimeError("private dispatch failure")

    monkeypatch.setattr(ultron._PROACTIVE_DISPATCHER, "dispatch_once_result", fail)
    monkeypatch.setattr(
        ultron._PROACTIVE_SPEECH,
        "speak",
        lambda _payload: calls.append(True) or True,
    )

    assert ultron.run_proactive_once() is None
    assert calls == []


def test_payload_passed_to_speech_is_unchanged(monkeypatch):
    payload = _payload()
    before = deepcopy(payload)
    received = []
    monkeypatch.setattr(
        ultron._PROACTIVE_DISPATCHER,
        "dispatch_once_result",
        lambda: ProactiveDispatchResult("presented", payload),
    )
    monkeypatch.setattr(
        ultron._PROACTIVE_SPEECH,
        "speak",
        lambda value: received.append(value) or True,
    )

    result = ultron.run_proactive_once()

    assert result == before
    assert received == [before]
    assert payload == before


def test_import_and_runtime_construction_do_not_invoke_proactive_execution():
    assert callable(ultron.run_proactive_once)
    assert isinstance(ultron._PROACTIVE_SPEECH, type(ultron._PROACTIVE_SPEECH))