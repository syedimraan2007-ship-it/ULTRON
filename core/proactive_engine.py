"""Deterministic policy decisions for desktop-context changes."""

from collections.abc import Callable, Mapping
import time


class ProactiveEngine:
    """Evaluate tracker results without performing any proactive action."""

    def __init__(
        self,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")

        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._last_eligible_at: float | None = None

    def evaluate(self, change: Mapping[str, object] | None) -> dict[str, object]:
        """Return a conservative, side-effect-free decision for a tracker result."""

        if not isinstance(change, Mapping):
            return self._decision(False, "unknown_context")

        if change.get("is_first") is True:
            return self._decision(False, "first_observation")

        if change.get("changed") is not True:
            return self._decision(False, "unchanged")

        previous = change.get("previous")
        current = change.get("current")
        if not self._is_meaningful_change(previous, current):
            return self._decision(False, "unknown_context")

        now = self._clock()
        if (
            self._last_eligible_at is not None
            and now - self._last_eligible_at < self._cooldown_seconds
        ):
            return self._decision(False, "cooldown")

        self._last_eligible_at = now
        return self._decision(True, "meaningful_change")

    @staticmethod
    def _is_meaningful_change(previous: object, current: object) -> bool:
        if not (
            ProactiveEngine._has_known_window_context(previous)
            and ProactiveEngine._has_known_window_context(current)
        ):
            return False

        return any(
            previous[field] != current[field]
            for field in ("application", "window_title")
        )

    @staticmethod
    def _has_known_window_context(context: object) -> bool:
        if not isinstance(context, Mapping):
            return False

        application = context.get("application")
        window_title = context.get("window_title")
        return (
            isinstance(application, str)
            and bool(application.strip())
            and isinstance(window_title, str)
            and bool(window_title.strip())
        )

    @staticmethod
    def _decision(eligible: bool, reason: str) -> dict[str, object]:
        return {
            "eligible": eligible,
            "reason": reason,
            "event": "desktop_changed",
        }