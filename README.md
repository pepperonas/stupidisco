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

- **Live-Transkription** — Deepgram Streaming-STT mit deutscher Sprachunterstützung (nova-3 Modell)
- **KI-Antworten** — Claude generiert prägnante Antworten in 2–3 Sätzen auf Deutsch, in Echtzeit gestreamt
- **Always-on-Top-Overlay** — Dunkles rahmenloses Fenster, verschieb- und größenveränderbar
- **Fenstersteuerung** — macOS-Style Traffic-Light-Buttons (Schließen, Minimieren, Maximieren)
- **Hotkey-Unterstützung** — `Cmd+Shift+R` (macOS) / `Ctrl+Shift+R` (Windows/Linux) zum Umschalten der Aufnahme
- **Geräteauswahl** — Jedes angeschlossene Mikrofon per Dropdown wählbar
- **Kopieren-Button** — Generierte Antwort mit einem Klick in die Zwischenablage kopieren
- **Regenerieren** — Antwort mit demselben Transkript neu generieren
- **Session-Logging** — Alle Frage-Antwort-Paare werden in `~/.stupidisco/sessions/` gespeichert
- **Latenz-Logging** — Misst die Zeit von Stop-Klick bis zur ersten/vollständigen Antwort

### Download

Fertige Binaries für macOS, Windows und Linux gibt es auf der [Releases-Seite](https://github.com/pepperonas/stupidisco/releases).

### Voraussetzungen

- Python 3.10+ (getestet mit Python 3.14)
- macOS, Windows oder Linux
- [Deepgram API-Key](https://console.deepgram.com/) (kostenlose Stufe mit $200 Guthaben)
- [Anthropic API-Key](https://console.anthropic.com/)

### Installation

```bash
git clone https://github.com/pepperonas/stupidisco.git
cd stupidisco

# Virtuelle Umgebung erstellen (empfohlen)
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt

# API-Keys konfigurieren
cp .env.example .env
# .env bearbeiten und Keys eintragen
```

### Nutzung

```bash
python stupidisco.py
```

1. Mikrofon aus dem Dropdown wählen (oder Standard verwenden)
2. Mic-Button klicken oder `Cmd+Shift+R` drücken, um die Aufnahme zu starten
3. Frage auf Deutsch sprechen
4. Erneut klicken oder Hotkey drücken zum Stoppen — die Antwort streamt innerhalb von Sekunden
5. **Kopieren** nutzen, um die Antwort zu übernehmen, oder **Regenerieren** für eine neue

> **Tipp:** Ein Headset-Mikrofon verwenden, um Echo von Lautsprechern während Videocalls zu reduzieren.

> **macOS:** Beim ersten Start Mikrofonberechtigung für Terminal/IDE erteilen, wenn die Abfrage erscheint.

### Funktionsweise

```
┌─────────────┐     ┌──────────┐     ┌─────────┐
│  Mikrofon    │────>│ Deepgram │────>│  Claude  │
│  (16kHz)     │     │ (STT)    │     │ (Antwort)│
└─────────────┘     └──────────┘     └─────────┘
       │                  │                │
       └──── Audio ───────┘                │
              Chunks         Transkript    │
                                │          │
                          ┌─────v──────────v─────┐
                          │   PyQt6 Overlay-GUI   │
                          │  (Always-on-Top)      │
                          └───────────────────────┘
```

### Konfiguration

Alle Einstellungen befinden sich in `.env`:

```bash
DEEPGRAM_API_KEY=dein_deepgram_api_key
ANTHROPIC_API_KEY=dein_anthropic_api_key
```

Das Claude-Modell und der System-Prompt können durch Bearbeiten der Konstanten am Anfang von `stupidisco.py` geändert werden:

- `CLAUDE_MODEL` — Standard: `claude-3-5-haiku-20241022`
- `SYSTEM_PROMPT` — Anweisungen für die Antwortgenerierung
- `SAMPLE_RATE` — Audio-Abtastrate (Standard: 16000)
- `CHUNK_MS` — Audio-Chunk-Größe in ms (Standard: 100)

### Session-Logs

Alle Frage-Antwort-Paare werden automatisch in `~/.stupidisco/sessions/` als Textdateien gespeichert, benannt nach Zeitstempel (z.B. `2025-02-11_23-08.txt`). Jeder Eintrag enthält Fragennummer, Zeitstempel, Transkript und generierte Antwort.

---

## English

Real-time interview assistant overlay for macOS, Windows and Linux. Captures spoken questions from video calls (Google Meet, Teams, Zoom) via microphone, transcribes them live and generates compact German answers — displayed in a small always-on-top overlay window.

### Features

- **Live transcription** — Deepgram streaming STT with German language support (nova-3 model)
- **AI answers** — Claude generates concise answers in 2–3 sentences in German, streamed in real-time
- **Always-on-top overlay** — Dark frameless window, draggable and resizable
- **Window controls** — macOS-style traffic light buttons (close, minimize, maximize)
- **Hotkey support** — `Cmd+Shift+R` (macOS) / `Ctrl+Shift+R` (Windows/Linux) to toggle recording
- **Device selection** — Any connected microphone selectable via dropdown
- **Copy button** — Copy generated answer to clipboard with one click
- **Regenerate** — Re-generate answer with the same transcript
- **Session logging** — All Q&A pairs saved to `~/.stupidisco/sessions/`
- **Latency logging** — Measures time from stop click to first/full answer

### Download

Pre-built binaries for macOS, Windows and Linux are available on the [Releases page](https://github.com/pepperonas/stupidisco/releases).

### Requirements

- Python 3.10+ (tested with Python 3.14)
- macOS, Windows or Linux
- [Deepgram API key](https://console.deepgram.com/) (free tier with $200 credit)
- [Anthropic API key](https://console.anthropic.com/)

### Installation

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
# Edit .env and enter your keys
```

### Usage

```bash
python stupidisco.py
```

1. Select microphone from dropdown (or use default)
2. Click mic button or press `Cmd+Shift+R` to start recording
3. Speak your question in German
4. Click again or press hotkey to stop — the answer streams within seconds
5. Use **Copy** to grab the answer, or **Regenerate** for a new one

> **Tip:** Use a headset microphone to reduce echo from speakers during video calls.

> **macOS:** Grant microphone permission for Terminal/IDE when prompted on first launch.

### How it works

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

### Configuration

All settings are in `.env`:

```bash
DEEPGRAM_API_KEY=your_deepgram_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

The Claude model and system prompt can be changed by editing the constants at the top of `stupidisco.py`:

- `CLAUDE_MODEL` — Default: `claude-3-5-haiku-20241022`
- `SYSTEM_PROMPT` — Instructions for answer generation
- `SAMPLE_RATE` — Audio sample rate (default: 16000)
- `CHUNK_MS` — Audio chunk size in ms (default: 100)

### Session Logs

All Q&A pairs are automatically saved to `~/.stupidisco/sessions/` as text files, named by timestamp (e.g. `2025-02-11_23-08.txt`). Each entry contains question number, timestamp, transcript and generated answer.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | PyQt6 (dark theme, frameless, resizable) |
| STT | Deepgram Streaming API (SDK v5, nova-3, German) |
| AI | Anthropic Claude (claude-3-5-haiku, streaming) |
| Audio | sounddevice (PortAudio, 16kHz mono int16) |
| Hotkey | pynput (GlobalHotKeys) |
| Config | python-dotenv |

## Developer

**Martin Pfeffer** — [celox.io](https://celox.io)

## License / Lizenz

MIT

---

Named after / Benannt nach [Stupidisco](https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1) by Junior Jack.

[![Stupidisco](https://img.youtube.com/vi/GJfydUI2Hzs/0.jpg)](https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1)
