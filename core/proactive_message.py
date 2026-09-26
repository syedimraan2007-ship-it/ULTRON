"""Deterministic, metadata-only messages for proactive desktop changes."""


class ProactiveMessage:
    """Generate concise acknowledgements without inspecting the desktop."""

    MAX_MESSAGE_LENGTH = 512
    MAX_TEXT_LENGTH = 256
    MAX_REASON_LENGTH = 64

    _BROWSER_MARKERS = (
        "chrome",
        "edge",
        "firefox",
        "brave",
        "browser",
    )
    _CODE_MARKERS = (
        "code.exe",
        "visual studio code",
        "vs code",
        "cursor",
        "pycharm",
        "sublime",
        "vim",
    )
    _TERMINAL_MARKERS = (
        "powershell",
        "cmd.exe",
        "command prompt",
        "windows terminal",
        "terminal",
    )
    _EXPLORER_MARKERS = (
        "explorer.exe",
        "file explorer",
        "windows explorer",
    )

    def __init__(self) -> None:
        self._last_application: str | None = None
        self._last_window_title: str | None = None

    def generate(
        self,
        application: object,
        window_title: object,
        reason: object,
    ) -> str:
        """Return a bounded message, using only supplied desktop metadata."""

        application_text = self._bounded_text(application, self.MAX_TEXT_LENGTH)
        window_title_text = self._bounded_text(window_title, self.MAX_TEXT_LENGTH)
        reason_text = self._bounded_text(reason, self.MAX_REASON_LENGTH)
        if application_text is None or window_title_text is None:
            return "Desktop context changed."

        application_key = application_text.casefold()
        title_key = window_title_text.casefold()
        repeated_application = (
            self._last_application == application_key
            and self._last_window_title is not None
            and self._last_window_title != title_key
        )

        self._last_application = application_key
        self._last_window_title = title_key

        if repeated_application and (
            "window" in (reason_text or "").casefold()
            or "title" in (reason_text or "").casefold()
            or reason_text == "meaningful_change"
        ):
            return self._bounded_message(
                f"The {application_text} window changed context."
            )

        if self._matches(application_key, self._BROWSER_MARKERS):
            message = "A browser window is now active."
        elif self._matches(application_key, self._CODE_MARKERS):
            message = "A code editor is now active."
        elif self._matches(application_key, self._TERMINAL_MARKERS):
            message = "A terminal is now active."
        elif self._matches(application_key, self._EXPLORER_MARKERS):
            message = "File Explorer is now active."
        else:
            message = f"You switched to {application_text}."

        return self._bounded_message(message)

    @staticmethod
    def _matches(application: str, markers: tuple[str, ...]) -> bool:
        return any(marker in application for marker in markers)

    @classmethod
    def _bounded_text(cls, value: object, limit: int) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        if len(value) > limit:
            return None
        return value.strip()

    @classmethod
    def _bounded_message(cls, message: str) -> str:
        return message[: cls.MAX_MESSAGE_LENGTH]