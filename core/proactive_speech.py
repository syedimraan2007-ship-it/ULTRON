"""Explicit adapter from approved proactive payloads to the existing TTS API."""

from collections.abc import Callable


class ProactiveSpeech:
    """Validate one approved payload and synchronously request TTS."""

    MAX_MESSAGE_LENGTH = 512
    MAX_TEXT_LENGTH = 256

    def __init__(self, tts: Callable[[str], object] | None = None) -> None:
        self._tts = tts

    def speak(self, payload: object) -> bool:
        """Speak one valid payload explicitly, returning only success status."""

        message = self._valid_message(payload)
        if message is None:
            return False

        try:
            tts = self._tts
            if tts is None:
                from voice.text_to_speech import speak as tts

            return bool(tts(message))
        except Exception:
            return False

    @classmethod
    def _valid_message(cls, payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None
        if set(payload) != {"message", "application", "window_title"}:
            return None

        message = payload.get("message")
        application = payload.get("application")
        window_title = payload.get("window_title")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (message, application, window_title)
        ):
            return None
        if (
            len(message) > cls.MAX_MESSAGE_LENGTH
            or len(application) > cls.MAX_TEXT_LENGTH
            or len(window_title) > cls.MAX_TEXT_LENGTH
        ):
            return None

        return message.strip()