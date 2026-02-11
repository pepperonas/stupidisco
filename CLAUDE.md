# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**stupidisco** is a real-time interview assistant overlay for macOS (M-series). It captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live, and generates compact German answers displayed in a small always-on-top overlay window.

Target latency: < 2-3 seconds from pressing Stop to full answer display.

## Tech Stack

- **Language:** Python 3.10+ (tested with 3.14), single-file app: `stupidisco.py`
- **GUI:** PyQt6 — dark theme, frameless always-on-top overlay, resizable (~340x560px default)
- **STT:** Deepgram SDK v5 — WebSocket streaming, nova-3 model, German language
- **Answer AI:** Anthropic Claude (`claude-3-5-haiku-20241022`) with streaming responses
- **Audio:** `sounddevice` for microphone capture (16kHz, mono, int16, 100ms chunks)
- **Threading:** Multi-threaded (Qt main thread + recording thread + Deepgram listener thread + asyncio worker thread)
- **Config:** `.env` file for API keys (`DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`)
- **Hotkey:** Cmd+Shift+R (macOS) / Ctrl+Shift+R (Windows/Linux) via `pynput`

## Architecture & Flow

```
Main Thread (Qt Event Loop)
  ├── StupidiscoApp (QMainWindow) — GUI, signals/slots, hotkey
  └── Hotkey listener (pynput, daemon thread)

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

- **No local models** — MacBook storage is limited, use cloud APIs only
- **Deepgram SDK v5 sync API** — Uses `listen.v1.connect()` context manager with sync WebSocket. `start_listening()` is a blocking recv loop that must run in its own thread
- **Direct audio→Deepgram** — sounddevice callback sends bytes directly to `socket.send_media()`, no async queue needed
- **Microphone input only** — no system audio capture or virtual loopback drivers; headset mic recommended
- **Device selection dropdown** available but defaults to OS default mic
- **Manual trigger only** — no auto-detection of questions
- **German in, German out** — both questions and answers are in German
- **Robust system prompt** — Claude is instructed to ALWAYS answer, even with fragmentary transcripts

## Claude System Prompt (for answer generation)

The system prompt is defined inline in `stupidisco.py` (SYSTEM_PROMPT constant). Key rules:
- Extract the question from the transcript and answer in German
- Max 2-3 sentences, direct, factual, no preamble
- ALWAYS answer — never refuse due to incomplete/fragmentary transcripts
- See `input/target.txt` for example answer style/length across domains

## Dependencies

```
PyQt6>=6.6.0, sounddevice>=0.4.6, numpy>=1.24.0, python-dotenv>=1.0.0,
anthropic>=0.39.0, deepgram-sdk>=3.7.0, pynput>=1.7.6
```

## Commands

```bash
# Create venv and install
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your DEEPGRAM_API_KEY and ANTHROPIC_API_KEY

# Run
python stupidisco.py
```

## GUI Features

- **Window controls** — macOS-style traffic light buttons (close/minimize/maximize)
- **Resizable** — drag bottom-right corner to resize, minimum 320x460
- **Draggable** — drag anywhere else to move
- **Mic toggle** — large circular button with pulsing red animation during recording
- **Device dropdown** — select any connected microphone
- **Live transcript** — scrollable, updates with partials during recording
- **Streaming answer** — green text, streams token-by-token from Claude
- **Copy button** — copies answer to clipboard
- **Regenerate button** — re-generates answer with same transcript
- **Session logging** — Q&A pairs saved to `~/.stupidisco/sessions/`
- **Latency logging** — first-chunk and total latency logged to console

## Project Status

Implemented and working. Single-file app with full GUI, Deepgram STT, Claude streaming, hotkey, session logging, resizable window with window controls.
