import json
import queue
import sys
import time
from pathlib import Path

import sounddevice as sd
from vosk import Model, KaldiRecognizer


# =========================
# ULTRON WAKE WORD SETTINGS
# =========================

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "vosk-model-large"

WAKE_PHRASES = [
    "hey ultron",
    "wake up ultron",
    "ultron",
]

SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

audio_queue = queue.Queue()


# =========================
# AUDIO CALLBACK
# =========================

def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"[Audio] {status}", file=sys.stderr)

    audio_queue.put(bytes(indata))


# =========================
# WAKE DETECTION
# =========================

def contains_wake_word(text):
    text = text.lower().strip()

    for phrase in WAKE_PHRASES:
        if phrase in text:
            return True

    return False


def main():
    print("================================")
    print("       ULTRON WAKE SERVICE")
    print("================================")
    print()

    if not MODEL_PATH.exists():
        print(f"[ERROR] Vosk model not found:")
        print(MODEL_PATH)
        return

    print("[1/3] Loading Vosk model...")
    model = Model(str(MODEL_PATH))

    print("[2/3] Creating recognizer...")
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)

    print("[3/3] Starting microphone...")
    print()
    print('Say "Hey Ultron" to activate.')
    print('Say "Wake up Ultron" to activate.')
    print("Press CTRL+C to stop.")
    print()

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
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()

                    if text:
                        print(f"[Heard] {text}")

                        now = time.time()

                        if (
                            contains_wake_word(text)
                            and now - last_trigger >= cooldown
                        ):
                            last_trigger = now

                            print()
                            print(">>> ULTRON WAKE WORD DETECTED <<<")
                            print()

    except KeyboardInterrupt:
        print()
        print("ULTRON wake service stopped.")


if __name__ == "__main__":
    main()