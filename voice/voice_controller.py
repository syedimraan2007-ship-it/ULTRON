from voice.microphone import record_audio
from voice.speech_to_text import transcribe_audio


def listen() -> str:
    """Record microphone input and convert it to text."""

    audio_file = record_audio()

    text = transcribe_audio(audio_file)

    return text.strip()