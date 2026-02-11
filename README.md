![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-macOS-000000?logo=apple&logoColor=white)
![STT](https://img.shields.io/badge/STT-Deepgram-13EF93?logo=deepgram&logoColor=white)
![AI](https://img.shields.io/badge/AI-Claude-d97706?logo=anthropic&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white)

# stupidisco

Echtzeit-Interview-Assistent als Overlay für macOS. Erfasst gesprochene Fragen aus Videocalls (Google Meet, Teams, Zoom) per Mikrofon, transkribiert sie live und generiert kompakte deutsche Antworten — angezeigt in einem kleinen Always-on-Top-Overlay-Fenster.

## Features

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

## Voraussetzungen

- Python 3.10+ (getestet mit Python 3.14)
- macOS (M-Series empfohlen), funktioniert auch unter Windows/Linux
- [Deepgram API-Key](https://console.deepgram.com/) (kostenlose Stufe mit $200 Guthaben)
- [Anthropic API-Key](https://console.anthropic.com/)

## Installation

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

## Nutzung

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

## Funktionsweise

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

### Architektur

Die App nutzt eine Multi-Thread-Architektur, um die GUI reaktionsfähig zu halten, während Echtzeit-Audio-Streaming und API-Aufrufe parallel laufen:

- **Main Thread** — PyQt6 Event Loop, GUI-Rendering, Hotkey-Handling via pynput
- **Recording Thread** — Öffnet Deepgram-WebSocket (sync SDK v5), erfasst Audio via `sounddevice`, sendet Chunks direkt an Deepgram via `send_media()`
- **Listener Thread** — Führt Deepgrams blockierende `start_listening()` Recv-Schleife aus, sendet Transkript-Signale zurück an die GUI
- **Async Worker Thread** — Dedizierter asyncio Event Loop für Claude Streaming-API (`messages.stream()`)

Die Kommunikation zwischen Threads erfolgt über Qt Signals/Slots, die thread-sicher sind.

### Threading-Modell

```
Main Thread (Qt)
  ├── GUI-Updates via Signals/Slots
  └── Hotkey-Listener (pynput, Daemon-Thread)

Recording Thread (pro Session)
  ├── Deepgram WebSocket Connect (sync)
  ├── sounddevice Audio-Callback → send_media()
  └── Listener Thread
       └── socket.start_listening() (blockierende Recv-Schleife)

Async Worker Thread
  └── asyncio Event Loop
       └── Claude Streaming (anthropic SDK)
```

### Warum dieses Design?

- **Deepgram SDK v5** nutzt eine synchrone WebSocket-API, bei der `start_listening()` blockiert. Das erfordert einen eigenen Thread
- **sounddevice** führt seinen Audio-Callback in einem PortAudio-Thread aus — Bytes werden direkt an Deepgram gesendet (kein Queue-Overhead)
- **Claudes Python SDK** ist asynchron — es braucht einen asyncio Event Loop, der im QThread-Worker lebt
- **PyQt6** kann die GUI nur vom Main Thread aus aktualisieren — Signals/Slots übernehmen die thread-sichere Kommunikation

## GUI

Das Overlay-Fenster bietet:

- **Traffic-Light-Buttons** (oben links) — Schließen (rot), Minimieren (gelb), Maximieren (grün)
- **Größenveränderbar** — Untere rechte Ecke ziehen zum Vergrößern/Verkleinern (Minimum 320x460)
- **Verschiebbar** — Überall sonst ziehen, um das Fenster zu bewegen
- **Geräte-Dropdown** — Eingabemikrofon auswählen
- **Mic-Button** — Großer runder Toggle mit pulsierender roter Animation während der Aufnahme
- **Transkript-Bereich** — Live-aktualisierter scrollbarer Text, der zeigt, was Deepgram erkennt
- **Antwort-Bereich** — Grüner Text, der Token für Token von Claude gestreamt wird
- **Kopieren / Regenerieren** — Aktionsbuttons unter der Antwort

## Tech Stack

| Komponente | Technologie |
|-----------|-----------|
| GUI | PyQt6 (Dark Theme, rahmenlos, größenveränderbar) |
| STT | Deepgram Streaming API (SDK v5, nova-3, Deutsch) |
| KI | Anthropic Claude (claude-3-5-haiku, Streaming) |
| Audio | sounddevice (PortAudio, 16kHz Mono int16) |
| Hotkey | pynput (GlobalHotKeys) |
| Config | python-dotenv |

## Konfiguration

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

## Session-Logs

Alle Frage-Antwort-Paare werden automatisch in `~/.stupidisco/sessions/` als Textdateien gespeichert, benannt nach Zeitstempel (z.B. `2025-02-11_23-08.txt`). Jeder Eintrag enthält Fragennummer, Zeitstempel, Transkript und generierte Antwort.

## Ziel-Latenz

< 2–3 Sekunden von Stop-Klick bis zur vollständigen Antwortanzeige.

Die App loggt Latenz-Metriken in die Konsole:
- Zeit bis zum ersten Antwort-Chunk
- Zeit bis zur vollständigen Antwort

## Entwickler

**Martin Pfeffer** — [celox.io](https://celox.io)

## Lizenz

MIT
