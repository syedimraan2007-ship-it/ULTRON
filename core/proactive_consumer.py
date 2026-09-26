"""Convert queued proactive metadata into passive message candidates."""

from collections.abc import Mapping

from core.proactive_activity_guard import ProactiveActivityGuard
from core.proactive_message import ProactiveMessage
from core.proactive_style import ProactiveStyle
from core.proactive_event_queue import ProactiveEventQueue


class ProactiveConsumer:
    """Consume approved proactive events without performing any action."""

    MAX_TEXT_LENGTH = 256
    MAX_MESSAGE_LENGTH = 512

    def __init__(
        self,
        queue: ProactiveEventQueue,
        activity_guard: ProactiveActivityGuard | None = None,
        message_generator: ProactiveMessage | None = None,
        message_style: ProactiveStyle | None = None,
    ) -> None:
        self._queue = queue
        self._activity_guard = activity_guard
        self._message_generator = message_generator or ProactiveMessage()
        self._message_style = message_style or ProactiveStyle()

    def consume_next(self) -> dict[str, str] | None:
        """Return one candidate, removing it only after validation succeeds."""

        if self._activity_guard is not None:
            try:
                if not self._activity_guard.is_allowed():
                    return None
            except Exception:
                return None

        metadata = self._queue.peek()
        candidate = self._candidate_from_metadata(metadata)
        if candidate is None:
            return None

        self._queue.pop()
        return candidate

    def _candidate_from_metadata(
        self,
        metadata: object,
    ) -> dict[str, str] | None:
        if not isinstance(metadata, Mapping):
            return None

        event = metadata.get("event")
        reason = metadata.get("reason")
        application = metadata.get("application")
        window_title = metadata.get("window_title")
        if event != "desktop_changed":
            return None
        if not all(
            isinstance(value, str) and value.strip()
            for value in (reason, application, window_title)
        ):
            return None

        application_text = application.strip()[: self.MAX_TEXT_LENGTH]
        window_title_text = window_title.strip()[: self.MAX_TEXT_LENGTH]
        message = self._message_generator.generate(
            application_text,
            window_title_text,
            reason,
        )
        if not isinstance(message, str) or not message.strip():
            return None
        message = self._message_style.format(
            message,
            application_text,
            window_title_text,
            reason,
        )
        if not isinstance(message, str) or not message.strip():
            return None

        return {
            "event": event,
            "message": message[: self.MAX_MESSAGE_LENGTH],
            "application": application_text,
            "window_title": window_title_text,
        }