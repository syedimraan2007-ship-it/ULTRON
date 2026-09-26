from types import SimpleNamespace

import pytest

from core import ultron
from core.events import EventBus
from core.proactive_activity_guard import ProactiveActivityGuard
from core.proactive_consumer import ProactiveConsumer
from core.proactive_cooldown import ProactiveCooldown
from core.proactive_dispatcher import ProactiveDispatcher
from core.proactive_event_queue import ProactiveEventQueue
from core.proactive_policy import ProactivePolicy
from core.proactive_presenter import ProactivePresenter
from core.proactive_relevance import ProactiveRelevance
from core.proactive_speech import ProactiveSpeech
from core.desktop_context_tracker import DesktopContextTracker
from core.proactive_engine import ProactiveEngine


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
    consumer = ProactiveConsumer(queue, guard)
    presenter = ProactivePresenter(guard)
    dispatcher = ProactiveDispatcher(
        consumer,
        presenter,
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
    monkeypatch.setattr(ultron, "_PROACTIVE_CONSUMER", consumer)
    monkeypatch.setattr(ultron, "_PROACTIVE_PRESENTER", presenter)
    monkeypatch.setattr(ultron, "_PROACTIVE_COOLDOWN", cooldown)
    monkeypatch.setattr(ultron, "_PROACTIVE_DISPATCHER", dispatcher)
    monkeypatch.setattr(ultron, "_PROACTIVE_SPEECH", speech)

    yield {
        "bus": event_bus,
        "queue": queue,
        "guard": guard,
        "speech_calls": speech_calls,
    }

    queue.unsubscribe(event_bus)
    guard.unsubscribe(event_bus)


def _install_chat(monkeypatch, calls):
    def fake_chat(**_kwargs):
        calls.append(True)
        return SimpleNamespace(
            message=SimpleNamespace(
                content="normal response",
                role="assistant",
                tool_calls=[],
            )
        )

    monkeypatch.setattr(ultron, "chat", fake_chat)


def _run_request(monkeypatch, snapshot, messages=None):
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: snapshot)
    return ultron.run_agent(
        "normal request",
        messages or [{"role": "system", "content": "base"}],
    )


def test_eligible_change_attempts_one_trigger_after_normal_llm_response(
    monkeypatch,
    runtime,
):
    calls = []
    trigger_calls = []
    _install_chat(monkeypatch, calls)
    contexts = iter([_context(), _context("PowerShell.exe", "PowerShell", 2)])
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: next(contexts))
    monkeypatch.setattr(
        ultron,
        "trigger_proactive",
        lambda: trigger_calls.append(True) or None,
    )
    messages = [{"role": "system", "content": "base"}]

    assert ultron.run_agent("first", messages) == "normal response"
    assert ultron.run_agent("second", messages) == "normal response"
    assert trigger_calls == [True]
    assert len(calls) == 2


@pytest.mark.parametrize(
    "snapshots",
    [
        [_context(), _context()],
        [_context(), _context(process_id=2)],
    ],
    ids=["unchanged", "process_id_only"],
)
def test_non_meaningful_changes_do_not_attempt_trigger(
    monkeypatch,
    runtime,
    snapshots,
):
    trigger_calls = []
    _install_chat(monkeypatch, [])
    contexts = iter(snapshots)
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: next(contexts))
    monkeypatch.setattr(
        ultron,
        "trigger_proactive",
        lambda: trigger_calls.append(True),
    )
    messages = [{"role": "system", "content": "base"}]

    ultron.run_agent("first", messages)
    ultron.run_agent("second", messages)

    assert trigger_calls == []


def test_first_observation_does_not_attempt_trigger(monkeypatch, runtime):
    trigger_calls = []
    _install_chat(monkeypatch, [])
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: _context())
    monkeypatch.setattr(
        ultron,
        "trigger_proactive",
        lambda: trigger_calls.append(True),
    )

    ultron.run_agent("first", [{"role": "system", "content": "base"}])

    assert trigger_calls == []


def test_blocked_activity_keeps_event_and_produces_no_speech(monkeypatch, runtime):
    _install_chat(monkeypatch, [])
    contexts = iter([_context(), _context("PowerShell.exe", "PowerShell", 2)])
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: next(contexts))
    messages = [{"role": "system", "content": "base"}]

    ultron.run_agent("first", messages)
    ultron.run_agent("second", messages)

    assert runtime["queue"].__len__() == 1
    assert runtime["speech_calls"] == []


def test_irrelevant_change_produces_no_speech(monkeypatch, runtime):
    runtime["guard"].set_idle()
    _install_chat(monkeypatch, [])
    contexts = iter([_context(), _context("explorer.exe", "Desktop", 2)])
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: next(contexts))
    messages = [{"role": "system", "content": "base"}]

    ultron.run_agent("first", messages)
    ultron.run_agent("second", messages)

    assert runtime["speech_calls"] == []
    assert len(runtime["queue"]) == 0


def test_cooldown_prevents_duplicate_speech(monkeypatch, runtime):
    runtime["guard"].set_idle()
    _install_chat(monkeypatch, [])
    contexts = iter([
        _context(),
        _context("PowerShell.exe", "PowerShell", 2),
        _context("notepad.exe", "notes.txt - Notepad", 3),
    ])
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: next(contexts))
    messages = [{"role": "system", "content": "base"}]

    ultron.run_agent("first", messages)
    ultron.run_agent("second", messages)
    ultron.run_agent("third", messages)

    assert len(runtime["speech_calls"]) == 1
    assert len(runtime["queue"]) == 1


def test_proactive_failure_does_not_break_normal_request(monkeypatch, runtime):
    calls = []
    _install_chat(monkeypatch, calls)
    contexts = iter([_context(), _context("PowerShell.exe", "PowerShell", 2)])
    monkeypatch.setattr(ultron, "get_desktop_context", lambda: next(contexts))

    def fail():
        raise RuntimeError("proactive failure")

    monkeypatch.setattr(ultron, "trigger_proactive", fail)
    messages = [{"role": "system", "content": "base"}]

    ultron.run_agent("first", messages)
    assert ultron.run_agent("second", messages) == "normal response"
    assert len(calls) == 2