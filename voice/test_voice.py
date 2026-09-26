from voice.microphone import record_audio
from voice.speech_to_text import transcribe_audio


def main() -> None:
    audio_file = record_audio()

    text = transcribe_audio(audio_file)

    print()
    print("=" * 50)
    print("YOU SAID:")
    print(text)
    print("=" * 50)


if __name__ == "__main__":
    main()