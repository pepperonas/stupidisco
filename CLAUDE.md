# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**stupidisco** is a real-time interview assistant overlay for macOS (M-series). It captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live, and generates compact German answers displayed in a small always-on-top overlay window.

Target latency: < 2–3 seconds from pressing Stop to full answer display.

## Tech Stack

- **Language:** Python (single-file app: `stupidisco.py`)
- **GUI:** PyQt6 — dark theme, semi-transparent always-on-top overlay (~300×400px)
- **STT:** Deepgram streaming API (websocket, real-time partials, German language)
- **Answer AI:** Anthropic Claude (`claude-3-5-haiku-20241022`) with streaming responses
- **Audio:** `sounddevice` for microphone capture (default system input device)
- **Async:** asyncio for concurrent audio capture, Deepgram websocket, Claude streaming
- **Config:** `.env` file for API keys (`DEEPGRAM_API_KEY`, `ANTHROPIC_API_KEY`)
- **Hotkey:** Cmd+Shift+R (macOS) / Ctrl+Shift+R (Windows/Linux) via `pynput`

## Architecture & Flow

```
Main Thread (Qt Event Loop)
  ├── StupidiscoApp (QMainWindow) — GUI, Button-Clicks, Hotkey
  │
  └── AsyncWorker (lives in QThread)
        ├── asyncio.run_forever()
        ├── Audio Capture (sounddevice → asyncio.Queue)
        ├── Deepgram WebSocket (Queue → Deepgram → Transcript Signals)
        └── Claude Streaming (Transcript → Claude → Answer Signals)
```

1. User presses Start (button or hotkey) → capture microphone audio in small chunks
2. Stream audio chunks live to Deepgram → receive partial + final transcripts → display live in GUI
3. User presses Stop → send final transcript to Claude with system prompt → stream answer to GUI
4. Next Start press clears previous transcript/answer, ready for next question

## Key Design Decisions

- **No local models** — MacBook storage is limited, use cloud APIs only
- **Microphone input only** — no system audio capture or virtual loopback drivers required; headset mic recommended to reduce echo
- **Device selection dropdown** available but defaults to OS default mic
- **Manual trigger only** — no auto-detection of questions
- **German in, German out** — both questions and answers are in German

## Claude System Prompt (for answer generation)

The AI answer prompt is defined in `input/stupidisco-prompt.txt`. Answers must be: direct, 2–3 sentences max, factual, no preamble, no meta-commentary. See `input/target.txt` for example answer style/length across domains.

## Dependencies

```
PyQt6, sounddevice, numpy, python-dotenv, anthropic, deepgram-sdk, pynput
```

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python stupidisco.py

# Required: create .env with API keys
echo "DEEPGRAM_API_KEY=your_key" >> .env
echo "ANTHROPIC_API_KEY=your_key" >> .env
```

## Extra Features (beyond original spec)

- **Copy Button** — copy answer to clipboard with one click
- **Regenerate Button** — re-generate answer with same transcript
- **Session Logging** — Q&A pairs saved to `~/.stupidisco/sessions/`
- **Latency Logging** — first-chunk and total latency printed to console

## Project Status

Implemented — single-file app `stupidisco.py` with full GUI, Deepgram STT, Claude streaming, hotkey, session logging.
