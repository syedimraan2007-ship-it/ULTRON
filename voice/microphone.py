import sounddevice as sd
from scipy.io.wavfile import write


SAMPLE_RATE = 16000
DURATION = 5

OUTPUT_FILE = r"D:\ultron\voice\input.wav"


def record_audio() -> str:
    print("ULTRON > Listening...")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )

    sd.wait()

    write(
        OUTPUT_FILE,
        SAMPLE_RATE,
        audio,
    )

    print("ULTRON > Recording complete.")

    return OUTPUT_FILE