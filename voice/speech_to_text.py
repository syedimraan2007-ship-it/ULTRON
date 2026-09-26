import os
from pathlib import Path

import whisper


# Explicit FFmpeg location
FFMPEG_DIR = r"D:\ffmpeg\bin"

# Add FFmpeg to this Python process's PATH
os.environ["PATH"] = (
    FFMPEG_DIR
    + os.pathsep
    + os.environ.get("PATH", "")
)


MODEL_NAME = "base"

_model = None


def get_model():
    global _model

    if _model is None:
        print("ULTRON > Loading speech recognition model...")
        _model = whisper.load_model(MODEL_NAME)

    return _model


def transcribe_audio(audio_file: str) -> str:
    model = get_model()

    result = model.transcribe(
        audio_file,
        language="en",
        temperature=0.0,
        fp16=False,
    )

    return result["text"].strip()