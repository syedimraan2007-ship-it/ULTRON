"""Bounded immutable diagnostics for proactive dispatch attempts."""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class ProactiveDecision:
    """Public, sanitized outcome of one proactive dispatch attempt."""

    status: str
    application: str = ""
    window_title: str = ""
    reason: str = ""
    message: str = ""
    reasoner_reason: str = ""

    STATUSES: ClassVar[frozenset[str]] = frozenset({
        "presented",
        "cooldown",
        "no_candidate",
        "irrelevant",
        "rejected",
        "reasoner_rejected",
    })
    MAX_MESSAGE_LENGTH: ClassVar[int] = 512
    MAX_TEXT_LENGTH: ClassVar[int] = 256
    MAX_REASON_LENGTH: ClassVar[int] = 128

    def __post_init__(self) -> None:
        if self.status not in self.STATUSES:
            raise ValueError("unknown proactive decision status")

        object.__setattr__(self, "application", self._bounded(self.application, self.MAX_TEXT_LENGTH))
        object.__setattr__(self, "window_title", self._bounded(self.window_title, self.MAX_TEXT_LENGTH))
        object.__setattr__(self, "reason", self._bounded(self.reason, self.MAX_REASON_LENGTH))
        object.__setattr__(self, "message", self._bounded(self.message, self.MAX_MESSAGE_LENGTH))
        object.__setattr__(self, "reasoner_reason", self._bounded(self.reasoner_reason, self.MAX_REASON_LENGTH))

    @staticmethod
    def _bounded(value: object, limit: int) -> str:
        if not isinstance(value, str):
            return ""
        return value[:limit]


def decision_from(
    status: str,
    source: object = None,
    *,
    reason: str = "",
    reasoner_reason: str = "",
) -> ProactiveDecision:
    """Build a decision from only known public presentation fields."""

    application = ""
    window_title = ""
    message = ""
    if isinstance(source, dict):
        application = source.get("application", "")
        window_title = source.get("window_title", "")
        message = source.get("message", "")

    return ProactiveDecision(
        status=status,
        application=application,
        window_title=window_title,
        reason=reason,
        message=message,
        reasoner_reason=reasoner_reason,
    )