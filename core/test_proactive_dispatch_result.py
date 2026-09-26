import pytest

from core.proactive_dispatch_result import ProactiveDispatchResult


def _payload():
    return {
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }


def test_presented_result_contains_sanitized_payload():
    result = ProactiveDispatchResult("presented", _payload())

    assert result.status == "presented"
    assert dict(result.payload) == _payload()


@pytest.mark.parametrize(
    "status",
    ["cooldown", "no_candidate", "irrelevant", "rejected"],
)
def test_non_presented_results_have_no_payload(status):
    result = ProactiveDispatchResult(status)

    assert result.payload is None


def test_result_is_frozen_and_payload_is_immutable():
    result = ProactiveDispatchResult("presented", _payload())

    with pytest.raises(Exception):
        result.status = "rejected"
    with pytest.raises(TypeError):
        result.payload["message"] = "changed"


def test_result_rejects_unknown_status_and_unsafe_payloads():
    with pytest.raises(ValueError):
        ProactiveDispatchResult("unknown")
    with pytest.raises(ValueError):
        ProactiveDispatchResult("rejected", _payload())
    with pytest.raises(ValueError):
        ProactiveDispatchResult("presented", {"message": "unsafe"})
    with pytest.raises(ValueError):
        ProactiveDispatchResult("presented", {
            **_payload(),
            "message": "x" * 513,
        })