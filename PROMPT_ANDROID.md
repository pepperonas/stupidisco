# Prompt: Android-App "stupidisco"

## Ziel

Erstelle eine native Android-App (Kotlin, Jetpack Compose) mit exakt der gleichen Funktionalität wie die Desktop-App `stupidisco`. Die App ist ein Echtzeit-Interview-Assistent: Sie nimmt gesprochene Fragen per Mikrofon auf, transkribiert sie live mit Deepgram und generiert strukturierte Antworten mit Claude — alles in einem Overlay, das über anderen Apps schwebt.

---

## Funktionale Anforderungen

### 1. Overlay (Floating Window)

- Die App zeigt ein **schwebendes Overlay-Fenster** (wie Facebook Chat Heads), das über allen anderen Apps liegt
- Nutzt `SYSTEM_ALERT_WINDOW`-Permission (Draw over other apps)
- Dunkles Theme: Hintergrund `#18181c`, Rahmen `#333338`, abgerundete Ecken (12dp)
- Das Overlay ist **verschiebbar** (Drag) und **größenveränderbar**
- Minimale Größe: 320x460dp, Standard: 340x560dp
- Enthält folgende Elemente (von oben nach unten):
  - **Titelleiste**: "stupidisco" + Status-Text ("Ready", "Recording...", "Thinking...", "Error")
  - **Mikrofon-Dropdown**: Auswahl des Eingabegeräts (falls mehrere vorhanden)
  - **Mic-Button**: Großer runder Button (64dp), pulsiert rot während Aufnahme
  - **Transcript-Bereich**: Scrollbar, zeigt Live-Transkript, grauer Text `#c8c8cc`
  - **Answer-Bereich**: Scrollbar, zeigt KI-Antwort, grüner Text `#34c759`
  - **Action-Buttons**: "Copy" (in Zwischenablage) + "Regenerate" (Antwort neu generieren)
  - **Footer**: Version + "celox.io"-Link

### 2. Audio-Aufnahme

- Mikrofon-Capture mit `AudioRecord` (Android API)
- Format: **16kHz, Mono, 16-bit PCM (LINEAR16)**
- Chunk-Größe: **100ms** (1600 Samples pro Chunk)
- Audio-Chunks werden direkt an Deepgram gestreamt (kein lokales Buffering)
- Aufnahme startet/stoppt per Mic-Button-Toggle

### 3. Speech-to-Text (Deepgram)

- **Deepgram Streaming API** via WebSocket
- Modell: `nova-3`
- Sprache: `de` (Deutsch)
- Encoding: `linear16`, Sample Rate: `16000`, Channels: `1`
- `interim_results: true` (Partial Transcripts für Live-Anzeige)
- `smart_format: true`
- Partial Transcripts → sofort in Transcript-Bereich anzeigen
- Final Transcripts → akkumulieren bis Recording stoppt
- WebSocket-URL: `wss://api.deepgram.com/v1/listen?model=nova-3&language=de&encoding=linear16&sample_rate=16000&channels=1&interim_results=true&smart_format=true`
- Auth: Header `Authorization: Token <DEEPGRAM_API_KEY>`

### 4. KI-Antworten (Claude)

- **Anthropic Messages API** mit Streaming (`stream: true`)
- Modell: `claude-sonnet-4-5-20250929`
- Max Tokens: `600`
- System-Prompt:

```
Du bist ein erfahrener Senior-Entwickler in einem technischen Interview. Du erhältst ein Live-Transkript — möglicherweise mit Fragmenten oder Echo.

FORMAT (strikt einhalten):
1. Erste Zeile: Kernaussage in EINEM Satz
2. Dann Stichpunkte mit • für Details, Trade-offs oder Beispiele
3. Jeder Stichpunkt: max. 1 kurzer Satz, keine Füllwörter
4. Max. 5 Stichpunkte — nur das Wichtigste

BEISPIEL-OUTPUT:
Microservices entkoppeln Deployment und Skalierung pro Service.
• Unabhängige Teams können parallel releasen
• Horizontale Skalierung nur dort, wo Last entsteht
• Trade-off: verteilte Systeme sind operativ komplexer
• Lohnt sich ab ca. 3+ Teams, darunter Modulith bevorzugen

REGELN:
- Deutsch, präzise, keine Vorrede, keine Meta-Kommentare
- Antworte IMMER — auch bei unklarem Transkript
- Zeige Tiefenwissen: Trade-offs, Best Practices, Praxisbezug
- Klinge souverän, nicht wie ein Lehrbuch
```

- Antwort-Tokens werden **einzeln gestreamt** und sofort im Answer-Bereich angezeigt
- API-Endpoint: `POST https://api.anthropic.com/v1/messages`
- Auth: Header `x-api-key: <ANTHROPIC_API_KEY>`, `anthropic-version: 2023-06-01`
- SSE-Stream parsen: `event: content_block_delta` → `delta.text` extrahieren

### 5. API-Key Management

- Beim ersten Start: **Dialog zur Eingabe** beider API-Keys (Deepgram + Anthropic)
- Keys werden in `EncryptedSharedPreferences` gespeichert
- Wenn Keys vorhanden → direkt starten, kein Dialog
- Links im Dialog:
  - Deepgram: `https://console.deepgram.com/` (kostenlos, $200 Guthaben)
  - Anthropic: `https://console.anthropic.com/`

### 6. Session-Logging

- Jedes Q&A-Paar wird in einer Textdatei gespeichert
- Verzeichnis: App-interner Storage `files/sessions/`
- Dateiname: `YYYY-MM-dd_HH-mm.txt`
- Format pro Eintrag:
```
============================================================
#1  14:32:15
============================================================
FRAGE:
<transkript>

ANTWORT:
<antwort>
```

### 7. Copy & Regenerate

- **Copy**: Aktuelle Antwort in System-Zwischenablage kopieren, Button zeigt kurz "Copied!"
- **Regenerate**: Gleicher Transkript-Text, neue Claude-Anfrage, Antwort wird ersetzt
- Beide Buttons nur aktiv nach fertiger Antwort

### 8. Latency-Logging

- Zeitstempel bei Stop-Klick merken
- Logge: "First answer chunk latency: X.XXs" (Zeit bis erstes Token von Claude)
- Logge: "Total answer latency: X.XXs" (Zeit bis Antwort komplett)
- Ziel: < 2-3 Sekunden für First Chunk

---

## Technische Architektur

### Tech Stack

| Komponente | Technologie |
|-----------|-----------|
| Sprache | Kotlin |
| UI | Jetpack Compose |
| Overlay | Foreground Service + `SYSTEM_ALERT_WINDOW` |
| Audio | `AudioRecord` (Android SDK) |
| STT | Deepgram WebSocket (OkHttp) |
| KI | Anthropic Claude API (OkHttp SSE) |
| Networking | OkHttp + Kotlin Coroutines |
| Key Storage | EncryptedSharedPreferences |
| Min SDK | 26 (Android 8.0) |
| Target SDK | 34 |

### Threading-Modell

```
Main Thread (Compose UI)
  ├── Overlay-Rendering
  ├── State Management (StateFlow)
  └── User Interactions

Foreground Service
  ├── Notification (required for overlay)
  └── Lifecycle Management

Coroutine: Recording Scope
  ├── AudioRecord → PCM Chunks
  ├── Deepgram WebSocket (OkHttp)
  │   ├── Send: Audio Chunks
  │   └── Receive: Transcript JSON
  └── Partial/Final Transcript → StateFlow

Coroutine: Answer Scope
  └── Claude SSE Stream (OkHttp)
       └── Token-by-Token → StateFlow
```

### Permissions

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.INTERNET" />
```

### Projekt-Struktur

```
app/src/main/java/io/celox/stupidisco/
  ├── MainActivity.kt              — Entry, Permission-Checks, API-Key Dialog
  ├── OverlayService.kt            — Foreground Service, Overlay Window Management
  ├── ui/
  │   ├── OverlayContent.kt        — Compose UI des Overlays
  │   ├── ApiKeyDialog.kt          — Compose Dialog für Key-Eingabe
  │   └── Theme.kt                 — Dark Theme, Farben, Typografie
  ├── audio/
  │   └── AudioRecorder.kt         — AudioRecord Wrapper, PCM Chunks via Flow
  ├── stt/
  │   └── DeepgramClient.kt        — WebSocket Client, Transcript Parsing
  ├── ai/
  │   └── ClaudeClient.kt          — SSE Streaming, Antwort-Parsing
  ├── data/
  │   ├── ApiKeyStore.kt           — EncryptedSharedPreferences
  │   └── SessionLogger.kt         — Q&A Logging in Textdateien
  └── model/
      └── AppState.kt              — UI State (Recording, Transcript, Answer, Status)
```

---

## Design-Spezifikation

### Farben

| Element | Farbe |
|---------|-------|
| Hintergrund | `#18181C` |
| Rahmen | `#333338` |
| Text primär | `#E0E0E0` |
| Text sekundär | `#8A8A8E` |
| Transcript-Text | `#C8C8CC` |
| Answer-Text | `#34C759` |
| Mic-Button (idle) | `rgba(255,255,255,12%)` |
| Mic-Button (recording) | `rgba(255,59,48,70%)` — pulsierend |
| Action-Buttons | `rgba(255,255,255,10%)` Hintergrund, `#8A8A8E` Text |
| Transcript-Hintergrund | `rgba(255,255,255,3%)` |
| Answer-Hintergrund | `rgba(52,199,89,4%)` |

### Animationen

- **Mic-Puls**: Während Recording, 600ms Intervall, Toggle zwischen `rgba(255,59,48,86%)` und `rgba(255,59,48,47%)`
- **Copy-Feedback**: Button-Text wechselt zu "Copied!" für 1.5 Sekunden

---

## Flow

```
1. App-Start
   ├── Keys vorhanden? → Overlay starten
   └── Keys fehlen? → API-Key Dialog → Keys speichern → Overlay starten

2. Overlay aktiv (Status: "Ready")
   └── User tippt Mic-Button

3. Recording (Status: "Recording...", Mic pulsiert rot)
   ├── AudioRecord startet → PCM Chunks
   ├── Deepgram WebSocket öffnet
   ├── Chunks → WebSocket senden
   ├── Partial Transcripts → Live-Anzeige
   └── User tippt Mic-Button erneut

4. Verarbeitung (Status: "Thinking...")
   ├── AudioRecord stoppt
   ├── Deepgram WebSocket schließt
   ├── Akkumuliertes Transkript → Claude API
   └── SSE Stream → Token-by-Token Anzeige

5. Fertig (Status: "Ready")
   ├── Copy + Regenerate Buttons aktiv
   ├── Session geloggt
   └── Bereit für nächste Frage
```

---

## Wichtige Implementierungsdetails

1. **Overlay über anderen Apps**: Nutze `WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY` mit einem `Foreground Service` + Notification
2. **Deepgram WebSocket**: Nutze OkHttp `WebSocket` — sende raw PCM bytes im `onOpen`, empfange JSON mit Transcript
3. **Claude SSE**: Nutze OkHttp mit `text/event-stream` Accept-Header, parse `data: {...}` Zeilen
4. **Kein lokales ML-Modell**: Nur Cloud-APIs, minimaler Speicherverbrauch
5. **Fehlerbehandlung**: Bei Netzwerkfehler → Status "Error" für 3 Sekunden, dann "Ready"
6. **Kein Transkript**: Falls nach Stop kein Text erkannt → "No speech detected. Try again."
7. **Package Name**: `io.celox.stupidisco`

---

## Nicht implementieren

- Keine lokale STT (kein Whisper, kein on-device ML)
- Kein System-Audio-Capture (nur Mikrofon)
- Keine Auto-Erkennung von Fragen (nur manueller Start/Stop)
- Keine Sprachauswahl (immer Deutsch)
- Kein Widget / Quick Settings Tile (nur Overlay)
