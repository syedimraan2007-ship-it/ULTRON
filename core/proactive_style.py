"""Deterministic tone formatting for proactive desktop messages."""


class ProactiveStyle:
    """Make approved deterministic messages concise and conversational."""

    MAX_MESSAGE_LENGTH = 512
    MAX_TEXT_LENGTH = 256
    FALLBACK_MESSAGE = "Desktop context changed."

    _BROWSER_MARKERS = ("chrome", "edge", "firefox", "brave", "browser")
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

    def format(
        self,
        message: object,
        application: object,
        window_title: object,
        reason: object,
    ) -> str:
        """Return a bounded style variant without adding unsupported claims."""

        validated_message = self._validated_message(message)
        if validated_message is None:
            return self.FALLBACK_MESSAGE

        application_text = self._bounded_text(application)
        window_title_text = self._bounded_text(window_title)
        if application_text is None or window_title_text is None:
            return validated_message

        if "window changed context" in validated_message.casefold():
            return validated_message

        application_key = application_text.casefold()
        if self._matches(application_key, self._BROWSER_MARKERS):
            styled = "Browser is active."
        elif self._matches(application_key, self._CODE_MARKERS):
            styled = "Code editor is active."
        elif self._matches(application_key, self._TERMINAL_MARKERS):
            styled = "Terminal is active."
        elif self._matches(application_key, self._EXPLORER_MARKERS):
            styled = "File Explorer is active."
        else:
            styled = f"{application_text} is active."

        return styled[: self.MAX_MESSAGE_LENGTH]

    @classmethod
    def _validated_message(cls, value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        if len(value) > cls.MAX_MESSAGE_LENGTH:
            return None
        return value.strip()

    @classmethod
    def _bounded_text(cls, value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        if len(value) > cls.MAX_TEXT_LENGTH:
            return None
        return value.strip()

    @staticmethod
    def _matches(application: str, markers: tuple[str, ...]) -> bool:
        return any(marker in application for marker in markers)