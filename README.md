# stupidisco

Real-time interview assistant overlay for macOS. Captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live, and generates compact German answers — displayed in a small always-on-top overlay window.

## Features

- **Live Transcription** — Deepgram streaming STT with German language support (nova-3 model)
- **AI Answers** — Claude generates concise 2-3 sentence answers in German, streamed in real-time
- **Always-on-Top Overlay** — Dark frameless window, draggable and resizable
- **Window Controls** — macOS-style traffic light buttons (close, minimize, maximize)
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

The app uses a multi-threaded architecture to keep the GUI responsive while handling real-time audio streaming and API calls:

- **Main Thread** — PyQt6 event loop, GUI rendering, hotkey handling via pynput
- **Recording Thread** — Opens Deepgram WebSocket (sync SDK v5), captures audio via `sounddevice`, sends chunks directly to Deepgram via `send_media()`
- **Listener Thread** — Runs Deepgram's blocking `start_listening()` recv loop, emits transcript signals back to GUI
- **Async Worker Thread** — Dedicated asyncio event loop for Claude streaming API (`messages.stream()`)

Communication between threads happens via Qt signals/slots, which are thread-safe.

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

### Why This Design?

- **Deepgram SDK v5** uses a sync WebSocket API where `start_listening()` blocks. This requires its own thread
- **sounddevice** runs its audio callback in a PortAudio thread — we send bytes directly to Deepgram from there (no queue overhead)
- **Claude's Python SDK** is async — it needs an asyncio event loop, which lives in the QThread worker
- **PyQt6** can only update the GUI from the main thread — signals/slots handle cross-thread communication safely

## GUI

The overlay window features:

- **Traffic light buttons** (top-left) — Close (red), Minimize (yellow), Maximize (green)
- **Resizable** — Drag the bottom-right corner to resize (minimum 320x460)
- **Draggable** — Drag anywhere else to move the window
- **Device dropdown** — Select input microphone
- **Mic button** — Large circular toggle with pulsing red animation during recording
- **Transcript area** — Live-updating scrollable text showing what Deepgram hears
- **Answer area** — Green text streaming in token-by-token from Claude
- **Copy / Regenerate** — Action buttons below the answer

## Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | PyQt6 (dark theme, frameless, resizable) |
| STT | Deepgram Streaming API (SDK v5, nova-3, German) |
| AI | Anthropic Claude (claude-3-5-haiku, streaming) |
| Audio | sounddevice (PortAudio, 16kHz mono int16) |
| Hotkey | pynput (GlobalHotKeys) |
| Config | python-dotenv |

## Configuration

All configuration is in `.env`:

```bash
DEEPGRAM_API_KEY=your_deepgram_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

The Claude model and system prompt can be changed by editing the constants at the top of `stupidisco.py`:

- `CLAUDE_MODEL` — default: `claude-3-5-haiku-20241022`
- `SYSTEM_PROMPT` — instructions for answer generation
- `SAMPLE_RATE` — audio sample rate (default: 16000)
- `CHUNK_MS` — audio chunk size in ms (default: 100)

## Session Logs

All Q&A pairs are automatically saved to `~/.stupidisco/sessions/` in plain text files named by timestamp (e.g. `2025-02-11_23-08.txt`). Each entry includes the question number, timestamp, transcript, and generated answer.

## Target Latency

< 2-3 seconds from pressing Stop to full answer display.

The app logs latency metrics to the console:
- Time to first answer chunk
- Time to complete answer

## License

MIT
