# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**stupidisco** is a real-time interview assistant overlay for macOS, Windows and Linux. It captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live, and generates compact German answers displayed in a small always-on-top overlay window.

Target latency: < 2-3 seconds from pressing Stop to full answer display.

## Tech Stack

- **Language:** Python 3.10+ (tested with 3.14), single-file app: `stupidisco.py`
- **GUI:** PyQt6 — dark theme, frameless always-on-top overlay, resizable (~340x560px default)
- **STT:** Deepgram SDK v5 — WebSocket streaming, nova-3 model, German language
- **Answer AI:** Anthropic Claude (`claude-3-5-haiku-20241022`) with streaming responses
- **Audio:** `sounddevice` for microphone capture (16kHz, mono, int16, 100ms chunks)
- **Threading:** Multi-threaded (Qt main thread + recording thread + Deepgram listener thread + asyncio worker thread)
- **Config:** `.env` file or `~/.stupidisco/.env` for API keys (`DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`)
- **Hotkey:** Cmd+Shift+R via native NSEvent (macOS) / Ctrl+Shift+R via pynput (Windows/Linux)

## Architecture & Flow

```
Main Thread (Qt Event Loop)
  ├── StupidiscoApp (QMainWindow) — GUI, signals/slots
  └── Hotkey listener (NSEvent on macOS, pynput on others)

Recording Thread (per session, started on mic button press)
  ├── DeepgramClient.listen.v1.connect() — sync WebSocket
  ├── sounddevice.RawInputStream callback → socket.send_media()
  └── Listener Thread
       └── socket.start_listening() — blocking recv loop, emits transcript signals

Async Worker Thread (QThread, runs asyncio event loop)
  └── asyncio.run_forever()
       └── Claude messages.stream() — async streaming answer generation
```

### Flow

1. User presses Start (button or hotkey) → recording thread opens Deepgram WS + audio stream
2. Audio callback sends chunks directly to Deepgram → partial/final transcript signals → GUI
3. User presses Stop → recording thread exits → accumulated transcript → Claude streaming
4. Claude answer streams token-by-token into GUI → Copy/Regenerate buttons activate
5. Next Start clears previous transcript/answer, ready for next question

## Key Design Decisions

- **No local models** — use cloud APIs only (Deepgram + Claude)
- **Deepgram SDK v5 sync API** — `listen.v1.connect()` context manager with sync WebSocket. `start_listening()` is a blocking recv loop that must run in its own thread
- **Direct audio→Deepgram** — sounddevice callback sends bytes directly to `socket.send_media()`, no async queue needed
- **Microphone input only** — no system audio capture or virtual loopback drivers; headset mic recommended
- **Manual trigger only** — no auto-detection of questions
- **German in, German out** — both questions and answers are in German
- **API key dialog** — on first launch (or missing keys), a modal dialog prompts for Deepgram + Anthropic keys, saved to `~/.stupidisco/.env`
- **Native macOS hotkey** — uses NSEvent global monitor instead of pynput to avoid crashes on macOS 14+

## Commands

```bash
# Create venv and install
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure API keys (or let the app prompt on first launch)
cp .env.example .env

# Run
python stupidisco.py

# Build macOS .app bundle
pip install pyinstaller
pyinstaller stupidisco.spec

# Run tests
pytest -v
```

## Dependencies

```
PyQt6>=6.6.0, sounddevice>=0.4.6, numpy>=1.24.0, python-dotenv>=1.0.0,
anthropic>=0.39.0, deepgram-sdk>=3.7.0, pynput>=1.7.6
```
