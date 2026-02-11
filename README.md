# stupidisco

Real-time interview assistant overlay for macOS. Captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live, and generates compact German answers — displayed in a small always-on-top overlay window.

## Features

- **Live Transcription** — Deepgram streaming STT with German language support (nova-3 model)
- **AI Answers** — Claude generates concise 2-3 sentence answers in German, streamed in real-time
- **Always-on-Top Overlay** — Dark frameless window (~320x460px), draggable anywhere on screen
- **Hotkey Support** — `Cmd+Shift+R` (macOS) / `Ctrl+Shift+R` (Windows/Linux) to toggle recording
- **Device Selection** — Choose any connected microphone from a dropdown
- **Copy Button** — One-click copy of the generated answer to clipboard
- **Regenerate** — Re-generate answer with the same transcript
- **Session Logging** — All Q&A pairs saved to `~/.stupidisco/sessions/`
- **Latency Logging** — Measures time from Stop press to first/complete answer

## Requirements

- Python 3.10+ (tested with Python 3.14)
- macOS (M-series recommended), also works on Windows/Linux
- [Deepgram API key](https://console.deepgram.com/) (free tier with $200 credit)
- [Anthropic API key](https://console.anthropic.com/)

## Installation

```bash
git clone https://github.com/pepperonas/stupidisco.git
cd stupidisco

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and add your keys
```

## Usage

```bash
python stupidisco.py
```

1. Select your microphone from the dropdown (or use the default)
2. Click the mic button or press `Cmd+Shift+R` to start recording
3. Speak your question in German
4. Click again or press the hotkey to stop — the answer streams in within seconds
5. Use **Copy** to grab the answer, or **Regenerate** for a new one

> **Tip:** Use a headset microphone to reduce echo from speakers during video calls.

> **macOS:** Grant microphone permission to Terminal/your IDE when prompted on first run.

## How It Works

```
┌─────────────┐     ┌──────────┐     ┌─────────┐
│  Microphone  │────>│ Deepgram │────>│  Claude  │
│  (16kHz)     │     │ (STT)    │     │ (Answer) │
└─────────────┘     └──────────┘     └─────────┘
       │                  │                │
       └──── Audio ───────┘                │
              Chunks         Transcript    │
                                │          │
                          ┌─────v──────────v─────┐
                          │   PyQt6 Overlay GUI   │
                          │  (Always-on-Top)      │
                          └───────────────────────┘
```

### Architecture

- **Main Thread** — PyQt6 event loop, GUI rendering, hotkey handling
- **Recording Thread** — Opens Deepgram WebSocket, captures audio via `sounddevice`, sends chunks directly to Deepgram
- **Listener Thread** — Receives Deepgram transcript messages (blocking WebSocket read loop)
- **Async Worker Thread** — Dedicated asyncio event loop for Claude streaming API
- Communication between threads via Qt signals/slots

### Threading Model

```
Main Thread (Qt)
  ├── GUI updates via signals/slots
  └── Hotkey listener (pynput, daemon thread)

Recording Thread (per session)
  ├── Deepgram WebSocket connect (sync)
  ├── sounddevice audio callback → send_media()
  └── Listener Thread
       └── socket.start_listening() (blocking recv loop)

Async Worker Thread
  └── asyncio event loop
       └── Claude streaming (anthropic SDK)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | PyQt6 (dark theme, frameless) |
| STT | Deepgram Streaming API (nova-3, German) |
| AI | Anthropic Claude (claude-3-5-haiku) |
| Audio | sounddevice (PortAudio) |
| Hotkey | pynput |
| Config | python-dotenv |

## Target Latency

< 2-3 seconds from pressing Stop to full answer display.

The app logs latency metrics to the console:
- Time to first answer chunk
- Time to complete answer

## License

MIT
