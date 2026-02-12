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
  <img src="screenshot.png" alt="stupidisco — Echtzeit-Interview-Assistent als Overlay" width="360">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/%F0%9F%87%A9%F0%9F%87%AA-Deutsch-black?style=for-the-badge" alt="Deutsch">
  &nbsp;
  <a href="README.en.md">
    <img src="https://img.shields.io/badge/%F0%9F%87%AC%F0%9F%87%A7-English-grey?style=for-the-badge" alt="English">
  </a>
</p>

---

Echtzeit-Interview-Assistent als Overlay für macOS, Windows und Linux. Erfasst gesprochene Fragen aus Videocalls (Google Meet, Teams, Zoom) per Mikrofon, transkribiert sie live und generiert kompakte deutsche Antworten — angezeigt in einem kleinen Always-on-Top-Overlay-Fenster.

**Dein unfairer Vorteil im Vorstellungsgespräch.** Jede Frage wird live transkribiert und von KI in Echtzeit beantwortet — unsichtbar für dein Gegenüber. Aus jedem Anfänger wird ein Experte.

### Features

| Feature | Beschreibung |
|---------|-------------|
| **Live-Transkription** | Deepgram Streaming-STT (nova-3 Modell, Deutsch) |
| **KI-Antworten** | Claude generiert prägnante Antworten in 2–3 Sätzen, in Echtzeit gestreamt |
| **Always-on-Top-Overlay** | Dunkles rahmenloses Fenster, verschieb- und größenveränderbar |
| **Fenstersteuerung** | macOS-Style Traffic-Light-Buttons (Schließen, Minimieren, Maximieren) |
| **Hotkey** | `Cmd+Shift+R` (macOS) / `Ctrl+Shift+R` (Windows/Linux) |
| **Geräteauswahl** | Mikrofon per Dropdown wählbar |
| **Kopieren & Regenerieren** | Antwort in die Zwischenablage kopieren oder neu generieren |
| **API-Key-Dialog** | Keys werden beim ersten Start abgefragt und in `~/.stupidisco/.env` gespeichert |
| **Session-Logging** | Frage-Antwort-Paare in `~/.stupidisco/sessions/` |

### Download

Fertige Binaries für alle Plattformen:

| Plattform | Architektur | Format |
|-----------|------------|--------|
| macOS | arm64 (Apple Silicon) | `.app` im ZIP |
| Windows | x64 | `.exe` im ZIP |
| Linux | x64 | Binary im tar.gz |

Zur [**Releases-Seite**](https://github.com/pepperonas/stupidisco/releases)

### Voraussetzungen

- Python 3.10+
- [Deepgram API-Key](https://console.deepgram.com/) — kostenlose Stufe mit $200 Guthaben
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
          ┌────────────┐
          │  Mikrofon   │
          │  (16kHz)    │
          └──────┬─────┘
                 │ Audio-Chunks
                 v
          ┌────────────┐
          │  Deepgram   │
          │  nova-3 STT │
          └──────┬─────┘
                 │ Transkript
                 v
          ┌────────────┐
          │  Claude AI  │
          │  Streaming  │
          └──────┬─────┘
                 │ Antwort (Token für Token)
                 v
     ┌───────────────────────┐
     │  PyQt6 Overlay (AOT)  │
     │  Transkript + Antwort │
     └───────────────────────┘
```

### Konfiguration

API-Keys werden beim ersten Start per Dialog abgefragt. Alternativ `.env` im Projektverzeichnis:

```bash
DEEPGRAM_API_KEY=dein_key
ANTHROPIC_API_KEY=dein_key
```

Weitere Konstanten in `stupidisco.py`:

| Konstante | Standard | Beschreibung |
|-----------|---------|-------------|
| `CLAUDE_MODEL` | `claude-3-5-haiku-20241022` | Claude-Modell für Antworten |
| `SYSTEM_PROMPT` | *(inline)* | Anweisungen für die Antwortgenerierung |
| `SAMPLE_RATE` | `16000` | Audio-Abtastrate in Hz |
| `CHUNK_MS` | `100` | Audio-Chunk-Größe in Millisekunden |

### Architektur

<table>
<tr><td>

**Threading-Modell**

```
Main Thread (Qt)
  ├── GUI-Rendering
  ├── Signal/Slot-Dispatch
  └── Hotkey-Listener
       └── NSEvent (macOS)
       └── pynput (Win/Linux)

Recording Thread
  ├── Deepgram WS Connect
  ├── sounddevice Callback
  │   └── send_media()
  └── Listener Thread
       └── start_listening()

Async Worker (QThread)
  └── asyncio Event Loop
       └── Claude Streaming
```

</td><td>

**Tech Stack**

| Komponente | Technologie |
|-----------|-----------|
| GUI | PyQt6 |
| STT | Deepgram SDK v5 (nova-3) |
| KI | Anthropic Claude (haiku) |
| Audio | sounddevice / PortAudio |
| Hotkey | NSEvent / pynput |
| Config | python-dotenv |
| Build | PyInstaller |
| CI/CD | GitHub Actions |

</td></tr>
</table>

**Ziel-Latenz:** < 2–3 Sekunden von Stop-Klick bis zur vollständigen Antwortanzeige.

### Warum "stupidisco"?

> **stupidisco** — aus dem Italienischen *stupire* (erstaunen, verblüffen). *„Stupidisco"* ist die erste Person Singular: **„ich überrasche"**, **„ich erstaune"**, **„ich verblüffe"**.

Inspiriert von [Stupidisco](https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1) von Junior Jack.

---

## Entwickler

**Martin Pfeffer** — [celox.io](https://celox.io)

## Lizenz

MIT

<p align="center">
  <a href="https://www.youtube.com/watch?v=GJfydUI2Hzs&list=RDGJfydUI2Hzs&start_radio=1">
    <img src="https://img.youtube.com/vi/GJfydUI2Hzs/0.jpg" alt="Stupidisco von Junior Jack" width="320">
  </a>
</p>
