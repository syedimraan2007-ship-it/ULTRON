# ULTRON

ULTRON is a local-first voice assistant for Windows. It combines a wake-word listener, speech recognition, local Ollama inference, text-to-speech, computer-awareness tools, and SQLite-backed memory in a modular Python project.

## Features

- Local wake-word listening with Vosk
- Voice input through Whisper
- Local responses through Ollama
- Piper text-to-speech with barge-in support
- System, GPU, battery, process, application, browser, and desktop tools
- Read/write file tools restricted to the project workspace
- SQLite memory tools
- Proactive desktop-context pipeline with policy, relevance, cooldown, and activity guards
- Unit and integration tests across the core modules

## Requirements

- Windows 11
- Python 3.13 or a compatible Python version supported by the installed packages
- A local Ollama installation with the configured model available
- A working microphone and audio output
- FFmpeg available locally for audio processing and playback
- Vosk, Whisper, and Piper model files downloaded separately

Large models, recordings, databases, virtual environments, and FFmpeg binaries are deliberately excluded from Git. See `.gitignore`.

## Setup

```powershell
git clone https://github.com/syedimraan2007-ship-it/ULTRON.git
cd ULTRON

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install and start Ollama, then pull the model configured in `core/ultron.py`:

```powershell
ollama pull qwen2.5:7b
```

Place the required local Vosk model at `vosk-model-large\`. Configure the FFmpeg paths in the voice modules for the local installation. Place Piper voice assets under `voice\models\`.

## Running

From the repository root:

```powershell
# Wake-word mode
$env:ULTRON_VOICE_MODE = "wake"
python -m core.ultron

# Continuous voice mode
$env:ULTRON_VOICE_MODE = "continuous"
python -m core.ultron
```

The default wake phrase is `Hey Ultron`. Press `Ctrl+C` to stop the assistant.

## Testing

Run the non-interactive test suite from the repository root:

```powershell
python -m pytest
python -m compileall -q core memory tools voice
python -m core.test_registry
```

Microphone, playback, application-launch, and destructive system-control tests require explicit local execution and are not part of the safe default validation workflow.

## Project Layout

```text
core/      Assistant orchestration, tools, events, proactive behavior, and tests
memory/    SQLite memory manager, tools, and tests
tools/     System, desktop, file, application, and web capabilities
voice/     Microphone, wake-word, Whisper, Piper, and voice-session modules
wakeword-forge/  Isolated custom wake-word training workspace
```

## Safety Notes

ULTRON can interact with the local desktop and filesystem. Review tool permissions before enabling automation. Never commit API keys, personal recordings, databases, model files, or other private data.

## Status

This is an actively developed personal project. The custom `ultron.onnx` wake-word model is developed and tested separately before replacing the current listener model.