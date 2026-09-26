import pytest

from core.proactive_cooldown import ProactiveCooldown


def test_initial_cooldown_allows_one_presentation():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 100.0)

    assert cooldown.is_allowed() is True
    assert cooldown.remaining() == 0.0


def test_record_blocks_until_duration_has_elapsed():
    now = [100.0]
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: now[0])
    cooldown.record()

    assert cooldown.is_allowed() is False
    now[0] = 129.0
    assert cooldown.is_allowed() is False
    now[0] = 130.0
    assert cooldown.is_allowed() is True


def test_exact_duration_boundary_is_allowed():
    now = [10.0]
    cooldown = ProactiveCooldown(seconds=5.0, clock=lambda: now[0])
    cooldown.record()
    now[0] = 15.0

    assert cooldown.is_allowed() is True
    assert cooldown.remaining() == 0.0


def test_remaining_is_bounded_and_never_negative():
    now = [50.0]
    cooldown = ProactiveCooldown(seconds=10.0, clock=lambda: now[0])
    cooldown.record()

    assert cooldown.remaining() == 10.0
    now[0] = 55.0
    assert 0.0 < cooldown.remaining() <= 10.0
    now[0] = 1000.0
    assert cooldown.remaining() == 0.0


def test_reset_makes_cooldown_available_immediately():
    cooldown = ProactiveCooldown(seconds=30.0, clock=lambda: 1.0)
    cooldown.record()
    cooldown.reset()

    assert cooldown.is_allowed() is True
    assert cooldown.remaining() == 0.0


def test_injected_clock_is_deterministic():
    now = [0.0]
    cooldown = ProactiveCooldown(seconds=2.5, clock=lambda: now[0])
    cooldown.record()
    now[0] = 1.25

    assert cooldown.is_allowed() is False
    assert cooldown.remaining() == pytest.approx(1.25)


def test_backwards_clock_jump_resets_baseline_and_fails_closed():
    now = [100.0]
    cooldown = ProactiveCooldown(seconds=10.0, clock=lambda: now[0])
    cooldown.record()
    now[0] = 50.0

    assert cooldown.is_allowed() is False
    assert cooldown.remaining() == 10.0
    now[0] = 60.0
    assert cooldown.is_allowed() is True


def test_state_is_instance_local():
    first = ProactiveCooldown(seconds=10.0, clock=lambda: 1.0)
    second = ProactiveCooldown(seconds=10.0, clock=lambda: 1.0)
    first.record()

    assert first.is_allowed() is False
    assert second.is_allowed() is True


def test_cooldown_has_no_scheduler_or_event_bus_surface():
    cooldown = ProactiveCooldown()

    assert not hasattr(cooldown, "subscribe")
    assert not hasattr(cooldown, "start")
    assert not hasattr(cooldown, "poll")