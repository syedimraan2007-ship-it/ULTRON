import json
from copy import deepcopy

import pytest

from core.proactive_reasoner import ProactiveReasoner
from core.proactive_reasoner_cases import (
    PROACTIVE_REASONER_CASES,
    evaluate_cases,
    is_valid_candidate,
)


def test_case_catalog_has_expected_size_order_and_unique_ids():
    ids = [case["id"] for case in PROACTIVE_REASONER_CASES]

    assert len(PROACTIVE_REASONER_CASES) == 15
    assert len(ids) == len(set(ids))
    assert ids == [
        "browser_switch",
        "code_editor_switch",
        "terminal_switch",
        "file_explorer_switch",
        "chat_application",
        "browser_media",
        "same_app_title_change",
        "repeated_context",
        "unknown_application",
        "security_utility",
        "system_settings",
        "lock_security_window",
        "search_transient_ui",
        "long_window_title",
        "metadata_only",
    ]


def test_every_case_matches_the_bounded_candidate_contract():
    assert all(
        is_valid_candidate(case["candidate"])
        for case in PROACTIVE_REASONER_CASES
    )
    assert len(PROACTIVE_REASONER_CASES[13]["candidate"]["window_title"]) == 256


def test_case_metadata_is_not_part_of_any_candidate():
    forbidden = {"id", "category", "process_id", "private", "history"}

    for case in PROACTIVE_REASONER_CASES:
        assert not forbidden.intersection(case["candidate"])


def test_cases_are_immutable():
    case = PROACTIVE_REASONER_CASES[0]

    with pytest.raises(TypeError):
        case["id"] = "changed"
    with pytest.raises(TypeError):
        case["candidate"]["message"] = "changed"


def test_evaluation_helper_returns_only_ids_and_public_results():
    reasoner = ProactiveReasoner()

    results = evaluate_cases(reasoner)

    assert len(results) == len(PROACTIVE_REASONER_CASES)
    assert set(results[0]) == {"id", "result"}
    assert set(results[0]["result"]) == {"should_speak", "message", "reason"}
    assert all("category" not in result for result in results)


def test_evaluation_helper_is_deterministic_and_does_not_mutate_cases():
    before = deepcopy([
        {
            "id": case["id"],
            "candidate": dict(case["candidate"]),
            "category": case["category"],
        }
        for case in PROACTIVE_REASONER_CASES
    ])

    first = evaluate_cases(ProactiveReasoner())
    second = evaluate_cases(ProactiveReasoner())

    assert first == second
    assert before == [
        {
            "id": case["id"],
            "candidate": dict(case["candidate"]),
            "category": case["category"],
        }
        for case in PROACTIVE_REASONER_CASES
    ]


def test_mocked_llm_exercises_speak_silence_malformed_and_error_results():
    captured = []

    def fake_llm(**kwargs):
        user_input = json.loads(kwargs["messages"][1]["content"])
        captured.append(user_input)
        application = user_input["application"]
        if application == "chrome.exe":
            return {"should_speak": True, "message": "Browser noted.", "reason": "browser_change"}
        if application == "Discord":
            return {"should_speak": False, "message": "", "reason": "chat_trivial"}
        if application == "Taskmgr.exe":
            return "malformed"
        if application == "SystemSettings.exe":
            raise TimeoutError()
        return {"should_speak": True, "message": "Acknowledged.", "reason": "desktop_context_change"}

    results = evaluate_cases(ProactiveReasoner(llm=fake_llm))
    by_id = {result["id"]: result["result"] for result in results}

    assert by_id["browser_switch"]["should_speak"] is True
    assert by_id["chat_application"]["should_speak"] is False
    assert by_id["security_utility"]["reason"] == "reasoner_error"
    assert by_id["system_settings"]["reason"] == "reasoner_error"
    assert all("category" not in item for item in captured)
    assert all("process_id" not in item for item in captured)