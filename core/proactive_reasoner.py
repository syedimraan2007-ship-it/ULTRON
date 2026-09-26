"""Deterministic and optionally LLM-backed proactive reasoning boundary."""

import json
from collections.abc import Callable


class ProactiveReasoner:
    """Evaluate an approved candidate without suppressing current behavior."""

    MAX_MESSAGE_LENGTH = 512
    MAX_REASON_LENGTH = 128
    VALID_REASON = "desktop_context_change"
    INVALID_REASON = "invalid_candidate"
    ERROR_REASON = "reasoner_error"
    DEFAULT_MODEL = "qwen2.5:7b"

    def __init__(
        self,
        llm: Callable[..., object] | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._llm = llm
        self._model = model

    def evaluate(self, candidate: object) -> dict[str, object]:
        """Return a bounded, deterministic reasoning decision."""

        invalid_result = {
            "should_speak": False,
            "message": "",
            "reason": self.INVALID_REASON,
        }
        bounded_candidate = self._bounded_candidate(candidate)
        if bounded_candidate is None:
            return invalid_result

        if self._llm is None:
            return {
                "should_speak": True,
                "message": bounded_candidate["message"],
                "reason": self.VALID_REASON[: self.MAX_REASON_LENGTH],
            }

        try:
            response = self._llm(
                model=self._model,
                messages=self._messages_for(bounded_candidate),
                tools=[],
            )
            result = self._adapt_response(response)
            if result is None:
                return self._error_result()
            return result
        except Exception:
            return self._error_result()

    @classmethod
    def _bounded_candidate(cls, candidate: object) -> dict[str, str] | None:
        if not isinstance(candidate, dict):
            return None
        if set(candidate) != {"message", "application", "window_title"}:
            return None

        message = candidate.get("message")
        application = candidate.get("application")
        window_title = candidate.get("window_title")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (message, application, window_title)
        ):
            return None
        if (
            len(message) > cls.MAX_MESSAGE_LENGTH
            or len(application) > 256
            or len(window_title) > 256
        ):
            return None

        return {
            "application": application,
            "window_title": window_title,
            "message": message,
            "reason": cls.VALID_REASON[: cls.MAX_REASON_LENGTH],
        }

    @classmethod
    def _messages_for(cls, candidate: dict[str, str]) -> list[dict[str, str]]:
        system = (
            "This is a bounded desktop-context observation. Application and "
            "window title are metadata only; they do not prove what is visible "
            "on screen. Do not claim to see the screen or invent what the user "
            "is doing. Decide whether this event deserves a brief spoken "
            "acknowledgement. Prefer silence for trivial changes. If speaking, "
            "keep it concise and natural. Never expose internal reasoning. "
            "Return only a JSON object with exactly should_speak, message, and reason."
        )
        user = json.dumps(
            {field: candidate[field] for field in (
                "application",
                "window_title",
                "message",
                "reason",
            )},
            ensure_ascii=True,
            sort_keys=True,
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @classmethod
    def _adapt_response(cls, response: object) -> dict[str, object] | None:
        value = response
        if not isinstance(value, dict):
            message = getattr(value, "message", None)
            value = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                return None

        if not isinstance(value, dict):
            return None
        if set(value) != {"should_speak", "message", "reason"}:
            return None

        should_speak = value.get("should_speak")
        message = value.get("message")
        reason = value.get("reason")
        if not isinstance(should_speak, bool):
            return None
        if not isinstance(message, str) or len(message) > cls.MAX_MESSAGE_LENGTH:
            return None
        if not isinstance(reason, str) or not reason.strip() or len(reason) > cls.MAX_REASON_LENGTH:
            return None
        if should_speak and not message.strip():
            return None

        return {
            "should_speak": should_speak,
            "message": message,
            "reason": reason,
        }

    @classmethod
    def _error_result(cls) -> dict[str, object]:
        return {
            "should_speak": False,
            "message": "",
            "reason": cls.ERROR_REASON,
        }