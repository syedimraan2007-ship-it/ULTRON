"""Instance-local monotonic cooldown for proactive presentations."""

import math
import time
from collections.abc import Callable


class ProactiveCooldown:
    """Allow one presentation, then block until the duration has elapsed."""

    def __init__(
        self,
        seconds: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("seconds must be a finite non-negative number")

        self._seconds = seconds
        self._clock = clock or time.monotonic
        self._recorded_at: float | None = None
        self._last_clock: float | None = None

    def is_allowed(self) -> bool:
        if self._recorded_at is None:
            return True

        elapsed = self._elapsed()
        return elapsed is not None and elapsed >= self._seconds

    def record(self) -> None:
        now = self._read_clock()
        if now is None:
            return

        self._recorded_at = now
        self._last_clock = now

    def remaining(self) -> float:
        if self._recorded_at is None:
            return 0.0

        elapsed = self._elapsed()
        if elapsed is None:
            return self._seconds

        return max(0.0, min(self._seconds, self._seconds - elapsed))

    def reset(self) -> None:
        self._recorded_at = None
        self._last_clock = None

    def _elapsed(self) -> float | None:
        now = self._read_clock()
        if now is None:
            return None

        if self._last_clock is not None and now < self._last_clock:
            self._recorded_at = now
            self._last_clock = now
            return 0.0

        self._last_clock = now
        if self._recorded_at is None:
            return None

        return max(0.0, now - self._recorded_at)

    def _read_clock(self) -> float | None:
        try:
            value = float(self._clock())
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(value):
            return None
        return value