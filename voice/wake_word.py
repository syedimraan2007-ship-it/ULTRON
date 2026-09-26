import json
import queue
import time
from pathlib import Path

import sounddevice as sd
from vosk import Model, KaldiRecognizer


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "vosk-model-large"

SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

WAKE_PHRASES = [
    "hey ultron",
]

_model = None


def get_model():
    global _model

    if _model is None:
        print("ULTRON > Loading local wake-word model...")

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Vosk model not found: {MODEL_PATH}"
            )

        _model = Model(str(MODEL_PATH))

    return _model


def contains_wake_word(text: str) -> bool:
    text = text.lower().strip()

    return any(
        phrase in text
        for phrase in WAKE_PHRASES
    )


def wait_for_wake_word() -> None:
    model = get_model()

    recognizer = KaldiRecognizer(
        model,
        SAMPLE_RATE,
    )

    audio_queue = queue.Queue()

    def audio_callback(
        indata,
        frames,
        time_info,
        status,
    ):
        if status:
            print(
                f"\nULTRON AUDIO > {status}"
            )

        audio_queue.put(bytes(indata))

    print()
    print("ULTRON > Wake-word system online.")
    print("ULTRON > Say: 'Hey Ultron'")
    print("ULTRON > Listening...")

    last_trigger = 0
    cooldown = 3

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while True:
                data = audio_queue.get()

                if recognizer.AcceptWaveform(data):
                    result = json.loads(
                        recognizer.Result()
                    )

                    text = result.get(
                        "text",
                        "",
                    ).strip()

                    if text:
                        print(
                            f"\n[Wake Listener] {text}"
                        )

                    now = time.time()

                    if (
                        contains_wake_word(text)
                        and now - last_trigger >= cooldown
                    ):
                        last_trigger = now

                        print()
                        print(
                            "ULTRON > Wake word detected."
                        )

                        return

    except KeyboardInterrupt:
        print()
        print(
            "ULTRON > Wake listener stopped."
        )
        raise