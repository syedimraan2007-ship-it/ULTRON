from copy import deepcopy
from types import SimpleNamespace

from core.proactive_reasoner import ProactiveReasoner


def _candidate(**overrides):
    candidate = {
        "message": "Code editor is active.",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    candidate.update(overrides)
    return candidate


def test_valid_candidate_is_approved_with_exact_schema():
    result = ProactiveReasoner().evaluate(_candidate())

    assert result == {
        "should_speak": True,
        "message": "Code editor is active.",
        "reason": "desktop_context_change",
    }
    assert set(result) == {"should_speak", "message", "reason"}


def test_invalid_candidate_returns_safe_deterministic_result():
    assert ProactiveReasoner().evaluate(None) == {
        "should_speak": False,
        "message": "",
        "reason": "invalid_candidate",
    }


def test_missing_fields_are_rejected():
    reasoner = ProactiveReasoner()
    for field in ("message", "application", "window_title"):
        candidate = _candidate()
        candidate.pop(field)
        assert reasoner.evaluate(candidate)["should_speak"] is False


def test_wrong_types_and_empty_strings_are_rejected():
    reasoner = ProactiveReasoner()

    assert reasoner.evaluate([])["should_speak"] is False
    assert reasoner.evaluate(_candidate(message=1))["should_speak"] is False
    assert reasoner.evaluate(_candidate(application=[]))["should_speak"] is False
    assert reasoner.evaluate(_candidate(window_title=" "))["should_speak"] is False


def test_oversized_message_is_rejected_without_truncation():
    result = ProactiveReasoner().evaluate(_candidate(message="x" * 513))

    assert result == {
        "should_speak": False,
        "message": "",
        "reason": "invalid_candidate",
    }


def test_valid_message_is_preserved_exactly_and_bounded():
    message = "x" * 512
    result = ProactiveReasoner().evaluate(_candidate(message=message))

    assert result["should_speak"] is True
    assert result["message"] == message
    assert len(result["message"]) == 512
    assert len(result["reason"]) <= 128


def test_repeated_evaluation_is_deterministic():
    reasoner = ProactiveReasoner()
    candidate = _candidate()

    assert reasoner.evaluate(candidate) == reasoner.evaluate(candidate)


def test_candidate_is_not_mutated():
    reasoner = ProactiveReasoner()
    candidate = _candidate()
    before = deepcopy(candidate)

    reasoner.evaluate(candidate)

    assert candidate == before


def test_mocked_llm_response_is_adapted():
    calls = []

    def fake_llm(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(
                content='{"should_speak": true, "message": "Brief acknowledgement.", "reason": "useful_change"}'
            )
        )

    result = ProactiveReasoner(llm=fake_llm).evaluate(_candidate())

    assert result == {
        "should_speak": True,
        "message": "Brief acknowledgement.",
        "reason": "useful_change",
    }
    assert calls[0]["model"] == ProactiveReasoner.DEFAULT_MODEL
    assert calls[0]["tools"] == []


def test_mocked_llm_can_choose_silence():
    reasoner = ProactiveReasoner(
        llm=lambda **_kwargs: {
            "should_speak": False,
            "message": "",
            "reason": "trivial_change",
        }
    )

    assert reasoner.evaluate(_candidate()) == {
        "should_speak": False,
        "message": "",
        "reason": "trivial_change",
    }


def test_malformed_llm_outputs_fail_safely():
    outputs = [
        "not json",
        {"should_speak": True},
        {
            "should_speak": True,
            "message": "ok",
            "reason": "ok",
            "extra": "no",
        },
        {"should_speak": "yes", "message": "ok", "reason": "ok"},
        {"should_speak": True, "message": "", "reason": "ok"},
        {"should_speak": True, "message": "x" * 513, "reason": "ok"},
        {"should_speak": True, "message": "ok", "reason": "x" * 129},
    ]

    for output in outputs:
        result = ProactiveReasoner(llm=lambda **_kwargs: output).evaluate(_candidate())
        assert result == {
            "should_speak": False,
            "message": "",
            "reason": "reasoner_error",
        }


def test_llm_exception_timeout_and_cancellation_fail_safely():
    exceptions = [RuntimeError("private"), TimeoutError(), __import__("concurrent").futures.CancelledError()]

    for exception in exceptions:
        def failing_llm(_exception=exception, **_kwargs):
            raise _exception

        assert ProactiveReasoner(llm=failing_llm).evaluate(_candidate()) == {
            "should_speak": False,
            "message": "",
            "reason": "reasoner_error",
        }


def test_llm_input_is_bounded_and_excludes_process_and_history():
    captured = []

    def fake_llm(**kwargs):
        captured.append(kwargs)
        return {
            "should_speak": True,
            "message": "ok",
            "reason": "desktop_context_change",
        }

    candidate = _candidate(
        application="A" * 256,
        window_title="B" * 256,
        message="C" * 512,
    )
    ProactiveReasoner(llm=fake_llm).evaluate(candidate)

    user_content = captured[0]["messages"][1]["content"]
    assert len(user_content) < 1200
    assert "process_id" not in user_content
    assert "conversation" not in user_content
    assert "history" not in user_content


def test_deterministic_fallback_remains_unchanged_with_no_llm():
    candidate = _candidate()

    assert ProactiveReasoner().evaluate(candidate) == {
        "should_speak": True,
        "message": candidate["message"],
        "reason": "desktop_context_change",
    }