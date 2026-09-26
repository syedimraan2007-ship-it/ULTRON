"""Final passive validation boundary for proactive message candidates."""

from collections.abc import Mapping

from core.proactive_activity_guard import ProactiveActivityGuard


class ProactivePresenter:
    """Return bounded presentation data when proactive activity is allowed."""

    MAX_TEXT_LENGTH = 256
    MAX_MESSAGE_LENGTH = 512

    def __init__(self, activity_guard: ProactiveActivityGuard) -> None:
        self._activity_guard = activity_guard

    def present(self, candidate: object) -> dict[str, str] | None:
        """Validate a candidate and return user-facing data without presenting it."""

        try:
            if not self._activity_guard.is_allowed():
                return None
        except Exception:
            return None

        if not isinstance(candidate, Mapping):
            return None

        event = candidate.get("event")
        message = candidate.get("message")
        application = candidate.get("application")
        window_title = candidate.get("window_title")
        if event != "desktop_changed":
            return None
        if not all(
            isinstance(value, str) and value.strip()
            for value in (message, application, window_title)
        ):
            return None

        return {
            "message": message.strip()[: self.MAX_MESSAGE_LENGTH],
            "application": application.strip()[: self.MAX_TEXT_LENGTH],
            "window_title": window_title.strip()[: self.MAX_TEXT_LENGTH],
        }