![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-blue)
![CI](https://github.com/pepperonas/stupidisco/actions/workflows/test.yml/badge.svg)
![STT](https://img.shields.io/badge/STT-Deepgram-13EF93?logo=deepgram&logoColor=white)
![AI](https://img.shields.io/badge/AI-Claude-d97706?logo=anthropic&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white)

# stupidisco

<p align="center">
  <img src="screenshot.png" alt="stupidisco Screenshot" width="340">
</p>

**[Deutsch](#deutsch)** | **[English](#english)**

---

## Deutsch

Echtzeit-Interview-Assistent als Overlay für macOS, Windows und Linux. Erfasst gesprochene Fragen aus Videocalls (Google Meet, Teams, Zoom) per Mikrofon, transkribiert sie live und generiert kompakte deutsche Antworten — angezeigt in einem kleinen Always-on-Top-Overlay-Fenster.

### Features

- **Live-Transkription** — Deepgram Streaming-STT (nova-3 Modell, Deutsch)
- **KI-Antworten** — Claude generiert prägnante Antworten in 2–3 Sätzen, in Echtzeit gestreamt
- **Always-on-Top-Overlay** — Dunkles rahmenloses Fenster, verschieb- und größenveränderbar
- **Fenstersteuerung** — macOS-Style Traffic-Light-Buttons (Schließen, Minimieren, Maximieren)
- **Hotkey** — `Cmd+Shift+R` (macOS) / `Ctrl+Shift+R` (Windows/Linux)
- **Geräteauswahl** — Mikrofon per Dropdown wählbar
- **Kopieren & Regenerieren** — Antwort in die Zwischenablage kopieren oder neu generieren
- **API-Key-Dialog** — Beim ersten Start werden die Keys per Dialog abgefragt und in `~/.stupidisco/.env` gespeichert
- **Session-Logging** — Frage-Antwort-Paare in `~/.stupidisco/sessions/`

### Download

Fertige Binaries für macOS (arm64), Windows (x64) und Linux (x64) gibt es auf der [Releases-Seite](https://github.com/pepperonas/stupidisco/releases).

### Voraussetzungen

- Python 3.10+
- [Deepgram API-Key](https://console.deepgram.com/) (kostenlose Stufe mit $200 Guthaben)
- [Anthropic API-Key](https://console.anthropic.com/)

### Installation

```bash
git clone https://github.com/pepperonas/stupidisco.git
cd stupidisco
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### Nutzung

```bash
python stupidisco.py
```

1. Mikrofon aus dem Dropdown wählen (oder Standard verwenden)
2. Mic-Button klicken oder Hotkey drücken — Aufnahme startet
3. Frage sprechen
4. Erneut klicken/Hotkey — Antwort streamt innerhalb von Sekunden
5. **Kopieren** oder **Regenerieren**

> **Tipp:** Headset-Mikrofon verwenden, um Echo zu reduzieren.

> **macOS:** Beim ersten Start Mikrofonberechtigung erteilen.

### Funktionsweise

```
Mikrofon ──> Deepgram (STT) ──> Claude (Antwort)
   │              │                    │
   └── Audio ─────┘                    │
       Chunks        Transkript        │
                          │            │
                    ┌─────v────────────v─────┐
                    │   PyQt6 Overlay (AOT)  │
                    └────────────────────────┘
```

### Konfiguration

API-Keys werden beim ersten Start per Dialog abgefragt. Alternativ `.env` im Projektverzeichnis:

```bash
DEEPGRAM_API_KEY=dein_key
ANTHROPIC_API_KEY=dein_key
```

Weitere Konstanten in `stupidisco.py`: `CLAUDE_MODEL`, `SYSTEM_PROMPT`, `SAMPLE_RATE`, `CHUNK_MS`.

---

## English

Real-time interview assistant overlay for macOS, Windows and Linux. Captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live and generates compact German answers — displayed in a small always-on-top overlay window.

### Features

- **Live transcription** — Deepgram streaming STT (nova-3 model, German)
- **AI answers** — Claude generates concise answers in 2–3 sentences, streamed in real-time
- **Always-on-top overlay** — Dark frameless window, draggable and resizable
- **Window controls** — macOS-style traffic light buttons (close, minimize, maximize)
- **Hotkey** — `Cmd+Shift+R` (macOS) / `Ctrl+Shift+R` (Windows/Linux)
- **Device selection** — Any connected microphone selectable via dropdown
- **Copy & Regenerate** — Copy answer to clipboard or re-generate
- **API key dialog** — On first launch, prompts for keys and saves them to `~/.stupidisco/.env`
- **Session logging** — Q&A pairs saved to `~/.stupidisco/sessions/`

### Download

Pre-built binaries for macOS (arm64), Windows (x64) and Linux (x64) are available on the [Releases page](https://github.com/pepperonas/stupidisco/releases).

### Requirements

- Python 3.10+
- [Deepgram API key](https://console.deepgram.com/) (free tier with $200 credit)
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
Microphone ──> Deepgram (STT) ──> Claude (Answer)
   │                │                    │
   └── Audio ───────┘                    │
       Chunks          Transcript        │
                           │             │
                     ┌─────v─────────────v─────┐
                     │   PyQt6 Overlay (AOT)   │
                     └─────────────────────────┘
```

### Configuration

API keys are prompted on first launch via dialog. Alternatively, create `.env` in the project directory:

```bash
DEEPGRAM_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
```

Additional constants in `stupidisco.py`: `CLAUDE_MODEL`, `SYSTEM_PROMPT`, `SAMPLE_RATE`, `CHUNK_MS`.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | PyQt6 (dark theme, frameless, resizable) |
| STT | Deepgram Streaming API (SDK v5, nova-3, German) |
| AI | Anthropic Claude (claude-3-5-haiku, streaming) |
| Audio | sounddevice (PortAudio, 16kHz mono int16) |
| Hotkey | NSEvent (macOS) / pynput (Windows/Linux) |
| Config | python-dotenv |

## Developer

**Martin Pfeffer** — [celox.io](https://celox.io)

## License / Lizenz

MIT

---

Named after / Benannt nach [Stupidisco](https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1) by Junior Jack.

[![Stupidisco](https://img.youtube.com/vi/GJfydUI2Hzs/0.jpg)](https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1)
