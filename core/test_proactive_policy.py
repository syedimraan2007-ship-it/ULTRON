from copy import deepcopy

from core.proactive_policy import ProactivePolicy


def _payload(**overrides):
    payload = {
        "message": "You switched to Code.exe.",
        "application": "Code.exe",
        "window_title": "main.py",
    }
    payload.update(overrides)
    return payload


def test_valid_payload_is_allowed():
    assert ProactivePolicy().allow(_payload()) is True


def test_none_and_malformed_payloads_are_rejected():
    policy = ProactivePolicy()

    assert policy.allow(None) is False
    assert policy.allow([]) is False
    assert policy.allow({"message": "hello"}) is False


def test_missing_required_fields_are_rejected():
    policy = ProactivePolicy()
    for field in ("message", "application", "window_title"):
        payload = _payload()
        payload.pop(field)
        assert policy.allow(payload) is False


def test_over_limit_fields_are_rejected():
    policy = ProactivePolicy()

    assert policy.allow(_payload(message="x" * 513)) is False
    assert policy.allow(_payload(application="x" * 257)) is False
    assert policy.allow(_payload(window_title="x" * 257)) is False


def test_wrong_field_types_are_rejected():
    policy = ProactivePolicy()

    assert policy.allow(_payload(message=1)) is False
    assert policy.allow(_payload(application=[])) is False
    assert policy.allow(_payload(window_title=None)) is False


def test_internal_or_debug_messages_are_rejected():
    policy = ProactivePolicy()

    assert policy.allow(_payload(message="Debug: internal state")) is False
    assert policy.allow(_payload(message="Tool error: failed")) is False
    assert policy.allow(_payload(message="Traceback: internal failure")) is False
    assert policy.allow(_payload(message="EventType.SPEAKING_STARTED")) is False


def test_identical_payload_is_suppressed_within_instance():
    policy = ProactivePolicy()

    assert policy.allow(_payload()) is True
    assert policy.allow(_payload()) is False


def test_slightly_different_payload_is_evaluated_independently():
    policy = ProactivePolicy()

    assert policy.allow(_payload()) is True
    assert policy.allow(_payload(window_title="other.py")) is True


def test_reset_allows_previously_rejected_duplicate_again():
    policy = ProactivePolicy()
    policy.allow(_payload())
    assert policy.allow(_payload()) is False

    policy.reset()

    assert policy.allow(_payload()) is True


def test_payload_is_not_mutated():
    policy = ProactivePolicy()
    payload = _payload()
    before = deepcopy(payload)

    policy.allow(payload)

    assert payload == before


def test_policy_has_no_external_state_or_automatic_hooks():
    policy = ProactivePolicy()

    assert not hasattr(policy, "subscribe")
    assert not hasattr(policy, "poll")
    assert not hasattr(policy, "start")