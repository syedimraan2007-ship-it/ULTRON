"""Immutable diagnostics for one proactive dispatch attempt."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Mapping


@dataclass(frozen=True)
class ProactiveDispatchResult:
    """Small, sanitized outcome for one synchronous dispatch attempt."""

    status: str
    payload: Mapping[str, str] | None = None

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

    def __post_init__(self) -> None:
        if self.status not in self.STATUSES:
            raise ValueError("unknown proactive dispatch status")

        if self.status != "presented":
            if self.payload is not None:
                raise ValueError("only presented results may contain a payload")
            return

        if not isinstance(self.payload, Mapping):
            raise ValueError("presented results require a payload")

        expected = {"message", "application", "window_title"}
        if set(self.payload) != expected:
            raise ValueError("payload contains unsupported fields")

        for field, value in self.payload.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError("payload fields must be non-empty strings")
            limit = (
                self.MAX_MESSAGE_LENGTH
                if field == "message"
                else self.MAX_TEXT_LENGTH
            )
            if len(value) > limit:
                raise ValueError("payload field exceeds its maximum length")

        object.__setattr__(
            self,
            "payload",
            MappingProxyType(dict(self.payload)),
        )