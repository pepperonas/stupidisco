![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)
![CI](https://github.com/pepperonas/stupidisco/actions/workflows/test.yml/badge.svg)
![Release](https://github.com/pepperonas/stupidisco/actions/workflows/release.yml/badge.svg)
![STT](https://img.shields.io/badge/STT-Deepgram-13EF93?logo=deepgram&logoColor=white)
![AI](https://img.shields.io/badge/AI-Claude-d97706?logo=anthropic&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white)

# stupidisco

<p align="center">
  <img src="screenshot.png" alt="stupidisco — Real-time Interview Assistant Overlay" width="360">
</p>

<p align="center">
  <a href="README.md">
    <img src="https://img.shields.io/badge/%F0%9F%87%A9%F0%9F%87%AA-Deutsch-grey?style=for-the-badge" alt="Deutsch">
  </a>
  &nbsp;
  <img src="https://img.shields.io/badge/%F0%9F%87%AC%F0%9F%87%A7-English-black?style=for-the-badge" alt="English">
</p>

---

Real-time interview assistant overlay for macOS, Windows and Linux. Captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live and generates compact German answers — displayed in a small always-on-top overlay window.

**Your unfair advantage in job interviews.** Every question is transcribed live and answered by AI in real time — invisible to your interviewer. Any amateur becomes an expert.

### Features

| Feature | Description |
|---------|-------------|
| **Live transcription** | Deepgram streaming STT (nova-3 model, German) |
| **AI answers** | Claude generates concise answers in 2–3 sentences, streamed in real-time |
| **Always-on-top overlay** | Dark frameless window, draggable and resizable |
| **Window controls** | macOS-style traffic light buttons (close, minimize, maximize) |
| **Hotkey** | `Cmd+Shift+R` (macOS) / `Ctrl+Shift+R` (Windows/Linux) |
| **Device selection** | Any connected microphone selectable via dropdown |
| **Copy & Regenerate** | Copy answer to clipboard or re-generate |
| **API key dialog** | Prompts for keys on first launch, saves to `~/.stupidisco/.env` |
| **Session logging** | Q&A pairs saved to `~/.stupidisco/sessions/` |

### Download

Pre-built binaries for all platforms:

| Platform | Architecture | Format |
|----------|-------------|--------|
| macOS | arm64 (Apple Silicon) | `.app` in ZIP |
| Windows | x64 | `.exe` in ZIP |
| Linux | x64 | Binary in tar.gz |

Go to [**Releases**](https://github.com/pepperonas/stupidisco/releases)

### Requirements

- Python 3.10+
- [Deepgram API key](https://console.deepgram.com/) — free tier with $200 credit
- [Anthropic API key](https://console.anthropic.com/)

### Installation

```bash
git clone https://github.com/pepperonas/stupidisco.git
cd stupidisco
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### Usage

```bash
python stupidisco.py
```

1. Select microphone from dropdown (or use default)
2. Click mic button or press hotkey — recording starts
3. Speak your question
4. Click again / hotkey — answer streams within seconds
5. **Copy** or **Regenerate**

> **Tip:** Use a headset microphone to reduce echo from speakers.

> **macOS:** Grant microphone permission when prompted on first launch.

### How it works

```
          ┌────────────┐
          │ Microphone  │
          │  (16kHz)    │
          └──────┬─────┘
                 │ Audio chunks
                 v
          ┌────────────┐
          │  Deepgram   │
          │  nova-3 STT │
          └──────┬─────┘
                 │ Transcript
                 v
          ┌────────────┐
          │  Claude AI  │
          │  Streaming  │
          └──────┬─────┘
                 │ Answer (token by token)
                 v
     ┌───────────────────────┐
     │  PyQt6 Overlay (AOT)  │
     │ Transcript + Answer   │
     └───────────────────────┘
```

### Configuration

API keys are prompted on first launch via dialog. Alternatively, create `.env` in the project directory:

```bash
DEEPGRAM_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
```

Additional constants in `stupidisco.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `CLAUDE_MODEL` | `claude-sonnet-4-5-20250929` | Claude model for answers |
| `SYSTEM_PROMPT` | *(inline)* | Senior dev interview persona, structured bullet-point answers |
| `MAX_TOKENS` | `600` | Maximum answer length (tokens) |
| `SAMPLE_RATE` | `16000` | Audio sample rate in Hz |
| `CHUNK_MS` | `100` | Audio chunk size in milliseconds |

### Architecture

<table>
<tr><td>

**Threading Model**

```
Main Thread (Qt)
  ├── GUI rendering
  ├── Signal/Slot dispatch
  └── Hotkey listener
       └── NSEvent (macOS)
       └── pynput (Win/Linux)

Recording Thread
  ├── Deepgram WS connect
  ├── sounddevice callback
  │   └── send_media()
  └── Listener Thread
       └── start_listening()

Async Worker (QThread)
  └── asyncio event loop
       └── Claude streaming
```

</td><td>

**Tech Stack**

| Component | Technology |
|-----------|-----------|
| GUI | PyQt6 |
| STT | Deepgram SDK v5 (nova-3) |
| AI | Anthropic Claude (Sonnet 4.5) |
| Audio | sounddevice / PortAudio |
| Hotkey | NSEvent / pynput |
| Config | python-dotenv |
| Build | PyInstaller |
| CI/CD | GitHub Actions |

</td></tr>
</table>

**Target latency:** < 2–3 seconds from stop click to full answer display.

### Why "stupidisco"?

> **stupidisco** — from Italian *stupire* (to astonish, to amaze). *"Stupidisco"* is the first person singular: **"I astonish"**, **"I amaze"**, **"I astound"**.

Inspired by [Stupidisco](https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1) by Junior Jack.

---

## Developer

**Martin Pfeffer** — [celox.io](https://celox.io)

## License

MIT

<p align="center">
  <a href="https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1">
    <img src="https://img.youtube.com/vi/GJfydUI2Hzs/0.jpg" alt="Stupidisco by Junior Jack" width="320">
  </a>
</p>
