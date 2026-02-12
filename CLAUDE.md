# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**stupidisco** is a real-time interview assistant overlay for macOS, Windows and Linux. Single-file Python app (`stupidisco.py`) that captures spoken questions via microphone, transcribes with Deepgram, and generates structured German answers with Claude — displayed in a frameless always-on-top overlay.

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run
python stupidisco.py

# Tests (13 tests, no API keys/mic/GUI needed)
pytest -v                    # all tests
pytest test_stupidisco.py::test_version_matches_pyproject  # single test

# Build macOS .app bundle (uses stupidisco.spec)
pip install pyinstaller
pyinstaller stupidisco.spec --noconfirm

# Build Windows/Linux (no .spec, CLI flags)
pyinstaller --onefile --windowed --name stupidisco stupidisco.py
```

## Architecture

```
stupidisco.py          — entire app (single file)
test_stupidisco.py     — unit tests (run without side effects)
stupidisco.spec        — PyInstaller config for macOS .app bundle
```

### Threading Model

```
Main Thread (Qt Event Loop)
  ├── StupidiscoApp (QMainWindow) — GUI, signals/slots
  └── Hotkey listener (NSEvent on macOS, pynput on Win/Linux)

Recording Thread (per session)
  ├── DeepgramClient.listen.v1.connect() — sync WebSocket
  ├── sounddevice.RawInputStream callback → socket.send_media()
  └── Listener Thread → socket.start_listening() (blocking)

Async Worker (QThread + asyncio event loop)
  └── Claude messages.stream() — async streaming
```

### Flow

1. Start button/hotkey → recording thread opens Deepgram WS + audio stream
2. Audio callback sends PCM chunks → Deepgram → partial/final transcript signals → GUI
3. Stop → accumulated transcript → Claude streaming (token-by-token → GUI)
4. Copy/Regenerate buttons activate

## Key Design Decisions

- **Single file** — all code in `stupidisco.py`, no package structure
- **Cloud only** — no local models, Deepgram STT + Claude for answers
- **Deepgram SDK v5 sync API** — `listen.v1.connect()` context manager, `start_listening()` blocks in its own thread
- **Direct audio→Deepgram** — sounddevice callback sends bytes via `socket.send_media()`, no queue
- **German in, German out** — transcription and answers both in German
- **Native macOS hotkey** — NSEvent global monitor (avoids pynput crashes on macOS 14+), falls back to pynput on other platforms
- **API keys** — prompted via dialog on first launch, saved to `~/.stupidisco/.env`

## Version Management

Version must be kept in sync in two places:
- `stupidisco.py` → `__version__ = "x.y.z"`
- `pyproject.toml` → `version = "x.y.z"`

CI test `test_version_matches_pyproject` enforces this.

## CI/CD

- **test.yml** — runs `pytest` on push/PR to main (ubuntu, macos, windows). Linux needs `QT_QPA_PLATFORM=offscreen`.
- **release.yml** — triggered by `v*` tags. Builds macOS (.app via .spec), Windows (.exe, needs Pillow for icon), Linux (binary). Creates GitHub Release with all 3 artifacts.

## Release Process

```bash
# 1. Bump version in both files
# 2. Commit and push
# 3. Tag and push
git tag v0.0.X && git push origin v0.0.X
```
