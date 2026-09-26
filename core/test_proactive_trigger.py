from core import ultron


def _payload():
    return {
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }


def test_trigger_calls_run_proactive_once_exactly_once(monkeypatch):
    calls = []

    def fake_run_once():
        calls.append(True)
        return _payload()

    monkeypatch.setattr(ultron, "run_proactive_once", fake_run_once)

    assert ultron.trigger_proactive() == _payload()
    assert calls == [True]


def test_trigger_returns_payload_unchanged(monkeypatch):
    payload = _payload()
    monkeypatch.setattr(ultron, "run_proactive_once", lambda: payload)

    result = ultron.trigger_proactive()

    assert result is payload


def test_trigger_propagates_none(monkeypatch):
    monkeypatch.setattr(ultron, "run_proactive_once", lambda: None)

    assert ultron.trigger_proactive() is None


def test_trigger_converts_boundary_exception_to_none(monkeypatch):
    calls = []

    def fail():
        calls.append(True)
        raise RuntimeError("private runtime failure")

    monkeypatch.setattr(ultron, "run_proactive_once", fail)

    assert ultron.trigger_proactive() is None
    assert calls == [True]


def test_import_and_runtime_construction_do_not_trigger_proactive_execution():
    assert callable(ultron.trigger_proactive)
    assert callable(ultron.run_proactive_once)