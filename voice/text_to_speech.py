import subprocess
import sys
import threading
import time
from pathlib import Path

import sounddevice as sd


VOICE_NAME = "en_US-norman-medium"

BASE_DIR = Path(r"D:\ultron\voice\models")

RAW_FILE = BASE_DIR / "ultron_raw.wav"
OUTPUT_FILE = BASE_DIR / "ultron_response.wav"

FFMPEG = Path(r"D:\ffmpeg\bin\ffmpeg.exe")
FFPLAY = Path(r"D:\ffmpeg\bin\ffplay.exe")

BARGE_IN_SAMPLE_RATE = 16000
BARGE_IN_BLOCK_SIZE = 1600
BARGE_IN_THRESHOLD = 1500

_PLAYBACK_LOCK = threading.Lock()


def _monitor_for_barge_in(
    stop_event: threading.Event,
    interrupted_event: threading.Event,
) -> None:
    started_at = time.monotonic()

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(f"\nULTRON AUDIO > {status}")

        if time.monotonic() - started_at < 0.3:
            return

        samples = memoryview(indata).cast("h")

        if samples and sum(abs(sample) for sample in samples) / len(samples) >= BARGE_IN_THRESHOLD:
            interrupted_event.set()

    try:
        with sd.RawInputStream(
            samplerate=BARGE_IN_SAMPLE_RATE,
            blocksize=BARGE_IN_BLOCK_SIZE,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while not stop_event.wait(0.05):
                if interrupted_event.is_set():
                    return

    except Exception as exc:
        print(f"\nULTRON BARGE-IN ERROR > {exc}")


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def speak(text: str) -> bool:
    """Generate, process, and play ULTRON's voice."""

    text = text.strip()

    if not text:
        return False

    if not _PLAYBACK_LOCK.acquire(blocking=False):
        raise RuntimeError("TTS playback is already active.")

    try:
        if not FFMPEG.exists():
            raise FileNotFoundError(
                f"FFmpeg not found: {FFMPEG}"
            )

        if not FFPLAY.exists():
            raise FileNotFoundError(
                f"FFplay not found: {FFPLAY}"
            )

        # Generate the raw Piper voice.
        subprocess.run(
            [
                sys.executable,
                "-m",
                "piper",
                "--data-dir",
                str(BASE_DIR),
                "-m",
                VOICE_NAME,
                "-f",
                str(RAW_FILE),
                "--",
                text,
            ],
            check=True,
        )

        # Heavy but controlled ULTRON processing.
        filter_chain = (
            "asetrate=22050*0.88,"
            "aresample=22050,"
            "atempo=0.94,"
            "bass=g=3:f=120,"
            "equalizer=f=250:t=q:w=1:g=1,"
            "acompressor="
            "threshold=-18dB:"
            "ratio=3:"
            "attack=5:"
            "release=100,"
            "alimiter=limit=0.85,"
            "volume=1.15"
        )

        subprocess.run(
            [
                str(FFMPEG),
                "-y",
                "-i",
                str(RAW_FILE),
                "-af",
                filter_chain,
                str(OUTPUT_FILE),
            ],
            check=True,
        )

        stop_event = threading.Event()
        interrupted_event = threading.Event()
        monitor = threading.Thread(
            target=_monitor_for_barge_in,
            args=(stop_event, interrupted_event),
            daemon=True,
        )
        process = subprocess.Popen(
            [
                str(FFPLAY),
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "quiet",
                str(OUTPUT_FILE),
            ]
        )
        monitor.start()

        try:
            while process.poll() is None:
                if interrupted_event.wait(0.05):
                    _stop_process(process)
                    break
        finally:
            stop_event.set()
            _stop_process(process)
            monitor.join(timeout=2)

        if process.returncode not in {0, None} and not interrupted_event.is_set():
            raise subprocess.CalledProcessError(
                process.returncode,
                process.args,
            )

        return interrupted_event.is_set()

    finally:
        _PLAYBACK_LOCK.release()