"""Deterministic filtering for obviously low-value proactive candidates."""

from collections.abc import Mapping


class ProactiveRelevance:
    """Reject malformed or clearly system-only desktop transitions."""

    MAX_TEXT_LENGTH = 256
    MAX_MESSAGE_LENGTH = 512

    _SHELL_IDENTIFIERS = frozenset({
        "desktop",
        "explorer.exe",
        "program manager",
        "windows explorer",
    })
    _SECURITY_IDENTIFIERS = frozenset({
        "lockapp.exe",
        "logonui.exe",
        "winlogon.exe",
        "windows security",
        "windows sign-in",
    })
    _TRANSIENT_IDENTIFIERS = frozenset({
        "dwm.exe",
        "searchhost.exe",
        "startmenuexperiencehost.exe",
        "textinputhost.exe",
    })

    def is_relevant(self, candidate: object) -> bool:
        """Return whether a valid candidate is worth presenting."""

        if not isinstance(candidate, dict):
            return False

        event = candidate.get("event")
        message = candidate.get("message")
        application = candidate.get("application")
        window_title = candidate.get("window_title")
        if event != "desktop_changed":
            return False
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

        application_key = application.strip().casefold()
        title_key = window_title.strip().casefold()
        if not application_key or application_key in {"unknown", "<unknown>"}:
            return False
        if application_key in self._SHELL_IDENTIFIERS:
            return False
        if application_key in self._SECURITY_IDENTIFIERS:
            return False
        if application_key in self._TRANSIENT_IDENTIFIERS:
            return False

        security_phrases = ("lock screen", "sign-in", "sign in")
        if any(phrase in title_key for phrase in security_phrases):
            return False
        if title_key in {"desktop", "program manager", "windows security"}:
            return False

        return True