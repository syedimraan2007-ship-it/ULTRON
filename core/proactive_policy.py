"""Deterministic user-experience policy for presented proactive payloads."""

from collections.abc import Mapping


class ProactivePolicy:
    """Allow bounded, user-facing payloads once per instance-local duplicate."""

    MAX_MESSAGE_LENGTH = 512
    MAX_TEXT_LENGTH = 256

    _INTERNAL_MARKERS = (
        "traceback",
        "stack trace",
        "debug:",
        "[debug]",
        "tool error:",
        "proactive_dispatch_result",
        "eventtype.",
    )

    def __init__(self) -> None:
        self._last_payload: tuple[str, str, str] | None = None

    def allow(self, payload: object) -> bool:
        """Return whether a presenter payload may pass the final policy gate."""

        if not isinstance(payload, dict):
            return False

        expected_fields = {"message", "application", "window_title"}
        if set(payload) != expected_fields:
            return False

        message = payload.get("message")
        application = payload.get("application")
        window_title = payload.get("window_title")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (message, application, window_title)
        ):
            return False
        if (
            len(message) > self.MAX_MESSAGE_LENGTH
            or len(application) > self.MAX_TEXT_LENGTH
            or len(window_title) > self.MAX_TEXT_LENGTH
        ):
            return False

        message_text = message.strip()
        application_text = application.strip()
        window_title_text = window_title.strip()
        message_key = message_text.casefold()
        if any(marker in message_key for marker in self._INTERNAL_MARKERS):
            return False

        fingerprint = (
            message_text,
            application_text,
            window_title_text,
        )
        if fingerprint == self._last_payload:
            return False

        self._last_payload = fingerprint
        return True

    def reset(self) -> None:
        self._last_payload = None