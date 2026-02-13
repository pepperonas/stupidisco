#!/usr/bin/env python3
"""
stupidisco — Real-time Interview Assistant Overlay

Captures spoken questions from video calls via microphone, transcribes them
live with Deepgram, and generates compact German answers with Claude.
Displayed in a small always-on-top overlay window.

Usage:
    python stupidisco.py

Requirements:
    pip install -r requirements.txt

Setup:
    1. Create .env with DEEPGRAM_API_KEY and ANTHROPIC_API_KEY
    2. On macOS, grant microphone permission when prompted
    3. Tip: Use a headset mic to reduce echo from speakers
"""

__version__ = "0.0.9"

import asyncio
import logging
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from PyQt6.QtCore import (
    QObject,
    QThread,
    Qt,
    pyqtSignal,
    pyqtSlot,
    QTimer,
    QPoint,
    QUrl,
)
from PyQt6.QtGui import QDesktopServices, QFont, QIcon, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def _resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller bundle."""
    if getattr(sys, '_MEIPASS', None):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / relative_path


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stupidisco")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
# Also check ~/.stupidisco/.env (written by API key dialog, works in .app bundles)
_user_env = Path.home() / ".stupidisco" / ".env"
if _user_env.exists():
    load_dotenv(_user_env)

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
SYSTEM_PROMPT = (
    "Du bist ein erfahrener Senior-Entwickler (15+ Jahre) in einem "
    "Vorstellungsgespräch. Du erhältst ein Live-Transkript einer "
    "gesprochenen Frage. Das Transkript kann Fragmente, Wiederholungen, "
    "Echo, Versprecher oder fehlende Wörter enthalten.\n\n"
    "SCHRITT 1 — FRAGE VERSTEHEN (intern, nicht ausgeben):\n"
    "Lies das Transkript sehr genau. Rekonstruiere die tatsächlich "
    "gemeinte Frage. Berücksichtige Kontext, Fachbegriffe und was in "
    "einem Interview typischerweise gefragt wird. Bei Mehrdeutigkeit: "
    "wähle die wahrscheinlichste Interpretation.\n\n"
    "SCHRITT 2 — ANTWORT (das ist dein Output):\n"
    "Beantworte exakt die erkannte Frage. Nicht ein verwandtes Thema, "
    "nicht eine allgemeine Übersicht — sondern präzise das, was gefragt wurde.\n\n"
    "FORMAT:\n"
    "Kernaussage in einem Satz.\n"
    "• Detail, Trade-off oder Praxisbeispiel (max. 1 Satz)\n"
    "• Weitere Details (max. 4-5 Stichpunkte insgesamt)\n\n"
    "REGELN:\n"
    "- Deutsch, fachlich korrekt, auf den Punkt\n"
    "- Antworte IMMER — auch bei schlechtem Transkript\n"
    "- Keine Vorrede, keine Meta-Kommentare, kein Markdown\n"
    "- Zeige Tiefenwissen: Trade-offs, Best Practices, konkrete Erfahrung\n"
    "- Wenn die Frage nicht technisch ist (Soft Skills, Gehalt, "
    "Motivation), antworte trotzdem souverän und überzeugend"
)

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
CHUNK_MS = 100  # 100ms chunks
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)

# ---------------------------------------------------------------------------
# Session Logger
# ---------------------------------------------------------------------------


class SessionLogger:
    """Appends Q&A pairs to a session file in ~/.stupidisco/sessions/."""

    def __init__(self):
        self._dir = Path.home() / ".stupidisco" / "sessions"
        self._dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        self._path = self._dir / f"{ts}.txt"
        self._count = 0

    def log(self, transcript: str, answer: str):
        self._count += 1
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"#{self._count}  {datetime.now().strftime('%H:%M:%S')}\n")
            f.write(f"{'='*60}\n")
            f.write(f"FRAGE:\n{transcript}\n\n")
            f.write(f"ANTWORT:\n{answer}\n")


# ---------------------------------------------------------------------------
# Async Worker — runs Deepgram + Claude in a dedicated asyncio loop
# ---------------------------------------------------------------------------


class AsyncWorker(QObject):
    """Handles audio capture, Deepgram STT and Claude streaming in a QThread."""

    transcript_partial = pyqtSignal(str)
    transcript_final = pyqtSignal(str)
    answer_chunk = pyqtSignal(str)
    answer_done = pyqtSignal()
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: sd.RawInputStream | None = None
        self._dg_socket = None
        self._dg_ctx = None
        self._dg_thread: threading.Thread | None = None
        self._recording = False
        self._accumulated_transcript = ""
        self._last_transcript = ""
        self._stop_time: float = 0

    # -- Thread entry point --------------------------------------------------

    def run(self):
        """Called when the QThread starts. Creates and runs the asyncio loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        log.info("AsyncWorker event loop running")
        self._loop.run_forever()

    def schedule(self, coro):
        """Schedule a coroutine on the worker's event loop from any thread."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    # -- Recording control ---------------------------------------------------

    def start_recording(self, device_index: int | None):
        """Start recording — runs Deepgram connect in a thread (it blocks)."""
        if self._recording:
            return
        self._recording = True
        self._accumulated_transcript = ""
        self.status_changed.emit("Recording...")

        self._dg_thread = threading.Thread(
            target=self._recording_thread, args=(device_index,), daemon=True
        )
        self._dg_thread.start()

    def stop_recording(self):
        """Signal stop and generate answer."""
        if not self._recording:
            return
        self._recording = False
        self._stop_time = time.time()
        self.status_changed.emit("Thinking...")

        # Stop audio stream
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def regenerate(self):
        if self._last_transcript:
            self.schedule(self._generate_answer(self._last_transcript))

    # -- Recording thread (Deepgram is sync, runs here) ---------------------

    def _recording_thread(self, device_index: int | None):
        """Runs in a dedicated thread: opens Deepgram WS, captures audio, sends it."""
        from deepgram import DeepgramClient
        from deepgram.core.events import EventType

        try:
            dg = DeepgramClient(api_key=DEEPGRAM_API_KEY)
            ctx = dg.listen.v1.connect(
                model="nova-3",
                language="de",
                encoding="linear16",
                sample_rate=str(SAMPLE_RATE),
                channels=str(CHANNELS),
                interim_results="true",
                smart_format="true",
            )

            socket = ctx.__enter__()
            self._dg_socket = socket
            self._dg_ctx = ctx

            def on_message(message):
                try:
                    if not hasattr(message, "channel"):
                        return
                    alt = message.channel.alternatives[0]
                    text = alt.transcript
                    if not text:
                        return
                    is_final = getattr(message, "is_final", False)
                    if is_final:
                        self._accumulated_transcript += text + " "
                        self.transcript_final.emit(
                            self._accumulated_transcript.strip()
                        )
                    else:
                        partial = self._accumulated_transcript + text
                        self.transcript_partial.emit(partial.strip())
                except Exception as e:
                    log.warning(f"Transcript parse error: {e}")

            def on_error(error):
                log.error(f"Deepgram error: {error}")
                self.error_occurred.emit(f"Deepgram: {error}")

            socket.on(EventType.MESSAGE, on_message)
            socket.on(EventType.ERROR, on_error)

            # Open audio FIRST — callback sends directly to Deepgram socket
            def audio_callback(indata, frames, time_info, status):
                if status:
                    log.warning(f"Audio status: {status}")
                if self._recording and self._dg_socket:
                    try:
                        self._dg_socket.send_media(bytes(indata))
                    except Exception:
                        pass

            kwargs = dict(
                samplerate=SAMPLE_RATE,
                blocksize=CHUNK_SIZE,
                dtype=DTYPE,
                channels=CHANNELS,
                callback=audio_callback,
            )
            if device_index is not None:
                kwargs["device"] = device_index

            self._stream = sd.RawInputStream(**kwargs)
            self._stream.start()
            log.info(f"Audio stream opened (device={device_index})")

            # start_listening() blocks — it reads WS messages in a loop.
            # It will exit when the WS is closed (on stop).
            # Run it in yet another thread so we can still send audio.
            listen_thread = threading.Thread(
                target=self._listen_loop, args=(socket,), daemon=True
            )
            listen_thread.start()
            log.info("Deepgram connection opened, listening for transcripts")

            # Wait until recording stops
            while self._recording:
                time.sleep(0.05)

            # Stop audio
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            # Close Deepgram websocket
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._dg_socket = None
            self._dg_ctx = None

            listen_thread.join(timeout=3)
            log.info("Deepgram connection closed")

        except Exception as e:
            log.exception("Recording thread error")
            self.error_occurred.emit(f"Recording error: {e}")
            self._recording = False
            self.status_changed.emit("Ready")
            return

        # Now generate answer
        time.sleep(0.3)  # Brief wait for final transcript callbacks
        transcript = self._accumulated_transcript.strip()
        if not transcript:
            self.status_changed.emit("Ready")
            self.error_occurred.emit("No speech detected. Try again.")
            return

        self._last_transcript = transcript
        self.transcript_final.emit(transcript)
        self.schedule(self._generate_answer(transcript))

    def _listen_loop(self, socket):
        """Blocking Deepgram message receive loop — runs in its own thread."""
        try:
            socket.start_listening()
        except Exception as e:
            if self._recording:
                log.warning(f"Deepgram listen loop ended: {e}")

    # -- Claude -------------------------------------------------------------

    async def _generate_answer(self, transcript: str):
        self.status_changed.emit("Thinking...")
        self.answer_chunk.emit("")  # Clear previous answer

        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

            first_chunk_time = None
            full_answer = ""

            async with client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": transcript}],
            ) as stream:
                async for text in stream.text_stream:
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                        latency = first_chunk_time - self._stop_time
                        log.info(f"First answer chunk latency: {latency:.2f}s")
                    full_answer += text
                    self.answer_chunk.emit(full_answer)

            total_latency = time.time() - self._stop_time
            log.info(f"Total answer latency: {total_latency:.2f}s")

            self.answer_done.emit()
            self.status_changed.emit("Ready")
            return full_answer

        except Exception as e:
            log.exception("Claude error")
            self.error_occurred.emit(f"Claude: {e}")
            self.status_changed.emit("Ready")
            return ""

    # -- Cleanup ------------------------------------------------------------

    def shutdown(self):
        self._recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        if self._dg_ctx:
            try:
                self._dg_ctx.__exit__(None, None, None)
            except Exception:
                pass
        if self._dg_thread and self._dg_thread.is_alive():
            self._dg_thread.join(timeout=2)
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)


# ---------------------------------------------------------------------------
# Lightweight Markdown → HTML conversion (no external dependency)
# ---------------------------------------------------------------------------


def _markdown_to_html(text: str) -> str:
    """Convert common Markdown patterns to HTML for QTextBrowser display."""
    if not text:
        return ""

    # Escape HTML entities first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Fenced code blocks: ```...```
    def _code_block(m):
        code = m.group(1).strip("\n")
        return (
            '<pre style="background-color: rgba(255,255,255,15); '
            "padding: 6px; border-radius: 4px; font-family: monospace; "
            'font-size: 12px; white-space: pre-wrap;">'
            f"{code}</pre>"
        )

    text = re.sub(r"```(?:\w*)\n?(.*?)```", _code_block, text, flags=re.DOTALL)

    # Inline code: `code`
    text = re.sub(
        r"`([^`]+)`",
        r'<code style="background-color: rgba(255,255,255,15); '
        r"padding: 1px 4px; border-radius: 3px; font-family: monospace; "
        r'font-size: 12px;">\1</code>',
        text,
    )

    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # Italic: *text* (but not inside bold markers)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)

    # Bullet lists: lines starting with - or • or *
    lines = text.split("\n")
    result = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[-•\*]\s+", stripped):
            if not in_list:
                result.append("<ul style='margin: 2px 0; padding-left: 18px;'>")
                in_list = True
            item = re.sub(r"^[-•\*]\s+", "", stripped)
            result.append(f"<li>{item}</li>")
        else:
            if in_list:
                result.append("</ul>")
                in_list = False
            result.append(line)
    if in_list:
        result.append("</ul>")

    text = "\n".join(result)

    # Line breaks (but not inside <pre> or <ul> blocks)
    parts = re.split(r"(<pre.*?</pre>|<ul.*?</ul>)", text, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if not part.startswith(("<pre", "<ul")):
            parts[i] = part.replace("\n", "<br>")
    text = "".join(parts)

    return text


# ---------------------------------------------------------------------------
# Main Window — PyQt6 GUI
# ---------------------------------------------------------------------------

STYLESHEET = """
QMainWindow {
    background-color: #18181c;
    border: 1px solid #333338;
    border-radius: 12px;
}
QWidget#central {
    background: transparent;
}
QLabel {
    color: #e0e0e0;
    background: transparent;
}
QLabel#title {
    font-size: 15px;
    font-weight: bold;
    color: #ffffff;
}
QLabel#status {
    font-size: 12px;
    color: #8a8a8e;
}
QLabel#section {
    font-size: 11px;
    font-weight: bold;
    color: #8a8a8e;
    padding-top: 4px;
}
QLabel#transcript {
    font-size: 13px;
    color: #c8c8cc;
    padding: 6px;
    background-color: rgba(255, 255, 255, 8);
    border-radius: 6px;
}
QTextBrowser#answer {
    font-size: 13px;
    color: #34c759;
    padding: 6px;
    background-color: rgba(52, 199, 89, 10);
    border-radius: 6px;
    border: none;
}
QComboBox {
    background-color: rgba(255, 255, 255, 12);
    color: #e0e0e0;
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #2c2c2e;
    color: #e0e0e0;
    selection-background-color: #3a3a3c;
}
QPushButton#mic {
    background-color: rgba(255, 255, 255, 12);
    color: #ffffff;
    border: 2px solid rgba(255, 255, 255, 25);
    border-radius: 32px;
    font-size: 28px;
    min-width: 64px;
    max-width: 64px;
    min-height: 64px;
    max-height: 64px;
}
QPushButton#mic:hover {
    background-color: rgba(255, 255, 255, 20);
}
QPushButton#mic[recording="true"] {
    background-color: rgba(255, 59, 48, 180);
    border-color: rgba(255, 59, 48, 220);
}
QPushButton#action {
    background-color: rgba(255, 255, 255, 10);
    color: #8a8a8e;
    border: 1px solid rgba(255, 255, 255, 15);
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
}
QPushButton#action:hover {
    background-color: rgba(255, 255, 255, 18);
    color: #e0e0e0;
}
QPushButton#action:disabled {
    color: #48484a;
    background-color: rgba(255, 255, 255, 5);
}
QPushButton#winbtn_close {
    background-color: #ff5f57;
    border: none;
    border-radius: 7px;
}
QPushButton#winbtn_close:hover {
    background-color: #ff3b30;
}
QPushButton#winbtn_min {
    background-color: #febc2e;
    border: none;
    border-radius: 7px;
}
QPushButton#winbtn_min:hover {
    background-color: #f0a000;
}
QPushButton#winbtn_max {
    background-color: #28c840;
    border: none;
    border-radius: 7px;
}
QPushButton#winbtn_max:hover {
    background-color: #20a835;
}
"""


class ApiKeyDialog(QDialog):
    """Modal dialog for entering API keys when .env is missing or incomplete."""

    DIALOG_STYLE = """
    QDialog {
        background-color: #1e1e22;
    }
    QLabel {
        color: #e0e0e0;
        background: transparent;
    }
    QLabel#heading {
        font-size: 15px;
        font-weight: bold;
        color: #ffffff;
    }
    QLabel#info {
        font-size: 12px;
        color: #8a8a8e;
    }
    QLabel#section {
        font-size: 13px;
        font-weight: bold;
        color: #c8c8cc;
    }
    QLabel#hint {
        font-size: 11px;
        color: #8a8a8e;
    }
    QLabel#link {
        font-size: 12px;
        color: #34c759;
    }
    QLabel#link:hover {
        color: #30d158;
    }
    QLineEdit {
        background-color: rgba(255, 255, 255, 10);
        color: #e0e0e0;
        border: 1px solid rgba(255, 255, 255, 20);
        border-radius: 6px;
        padding: 8px 10px;
        font-size: 13px;
        font-family: monospace;
    }
    QLineEdit:focus {
        border-color: rgba(52, 199, 89, 150);
    }
    QPushButton#save {
        background-color: #34c759;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton#save:hover {
        background-color: #30d158;
    }
    QPushButton#save:disabled {
        background-color: rgba(52, 199, 89, 40);
        color: rgba(255, 255, 255, 40);
    }
    QPushButton#cancel {
        background-color: rgba(255, 255, 255, 10);
        color: #8a8a8e;
        border: 1px solid rgba(255, 255, 255, 15);
        border-radius: 6px;
        padding: 8px 20px;
        font-size: 13px;
    }
    QPushButton#cancel:hover {
        background-color: rgba(255, 255, 255, 18);
        color: #e0e0e0;
    }
    """

    def __init__(self, missing: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("stupidisco — API Keys")
        self.setFixedWidth(420)
        self.setStyleSheet(self.DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(24, 20, 24, 20)

        heading = QLabel("stupidisco — API Keys")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        info = QLabel("Für die Nutzung werden zwei API-Keys benötigt:")
        info.setObjectName("info")
        layout.addWidget(info)
        layout.addSpacing(8)

        # --- Deepgram ---
        dg_label = QLabel("Deepgram API Key")
        dg_label.setObjectName("section")
        layout.addWidget(dg_label)

        self.dg_input = QLineEdit()
        self.dg_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.dg_input.setPlaceholderText("dg_xxxxxxxxxxxxxxxx")
        self.dg_input.setText(DEEPGRAM_API_KEY)
        self.dg_input.textChanged.connect(self._update_save_state)
        layout.addWidget(self.dg_input)

        dg_link = QLabel('<a href="https://console.deepgram.com" style="color: #34c759; text-decoration: none;">Kostenlos erstellen auf console.deepgram.com</a>')
        dg_link.setObjectName("link")
        dg_link.setOpenExternalLinks(True)
        layout.addWidget(dg_link)

        dg_hint = QLabel("Sign up → Settings → API Keys → Create Key")
        dg_hint.setObjectName("hint")
        layout.addWidget(dg_hint)
        layout.addSpacing(10)

        # --- Anthropic ---
        ant_label = QLabel("Anthropic API Key")
        ant_label.setObjectName("section")
        layout.addWidget(ant_label)

        self.ant_input = QLineEdit()
        self.ant_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ant_input.setPlaceholderText("sk-ant-xxxxxxxxxxxxxxxx")
        self.ant_input.setText(ANTHROPIC_API_KEY)
        self.ant_input.textChanged.connect(self._update_save_state)
        layout.addWidget(self.ant_input)

        ant_link = QLabel('<a href="https://console.anthropic.com" style="color: #34c759; text-decoration: none;">Kostenlos erstellen auf console.anthropic.com</a>')
        ant_link.setObjectName("link")
        ant_link.setOpenExternalLinks(True)
        layout.addWidget(ant_link)

        ant_hint = QLabel("Sign up → API Keys → Create Key")
        ant_hint.setObjectName("hint")
        layout.addWidget(ant_hint)
        layout.addSpacing(16)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setObjectName("cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        btn_layout.addStretch()

        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("save")
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

        self._update_save_state()

    def _update_save_state(self):
        self.save_btn.setEnabled(
            bool(self.dg_input.text().strip()) and bool(self.ant_input.text().strip())
        )

    def save_env(self):
        """Write the entered keys to ~/.stupidisco/.env."""
        config_dir = Path.home() / ".stupidisco"
        config_dir.mkdir(parents=True, exist_ok=True)
        env_path = config_dir / ".env"
        self.env_path = env_path
        lines = []
        # Preserve existing .env content (non-key lines)
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("DEEPGRAM_API_KEY=") or stripped.startswith("ANTHROPIC_API_KEY="):
                    continue
                lines.append(line)
        lines.append(f"DEEPGRAM_API_KEY={self.dg_input.text().strip()}")
        lines.append(f"ANTHROPIC_API_KEY={self.ant_input.text().strip()}")
        env_path.write_text("\n".join(lines) + "\n")


class StupidiscoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self._recording = False
        self._drag_pos: QPoint | None = None
        self._resizing = False
        self._resize_origin = None
        self._resize_size = None
        self._last_answer = ""
        self._last_transcript = ""
        self._pulse_on = False
        self._session_logger = SessionLogger()
        self._normal_geometry = None

        self._init_ui()
        self._init_worker()
        self._init_hotkey()
        self._init_pulse_timer()

    # -- UI -----------------------------------------------------------------

    def _init_ui(self):
        self.setWindowTitle("stupidisco")
        self.setMinimumSize(320, 460)
        self.resize(340, 560)
        icon_path = _resource_path("icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setStyleSheet(STYLESHEET)

        self.setMouseTracking(True)

        # Frameless, always-on-top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Title bar with window controls
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title = QLabel("stupidisco")
        title.setObjectName("title")
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("status")

        # macOS-style traffic light buttons
        btn_close = QPushButton("")
        btn_close.setObjectName("winbtn_close")
        btn_close.setFixedSize(14, 14)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.close)

        btn_min = QPushButton("")
        btn_min.setObjectName("winbtn_min")
        btn_min.setFixedSize(14, 14)
        btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_min.clicked.connect(self.showMinimized)

        btn_max = QPushButton("")
        btn_max.setObjectName("winbtn_max")
        btn_max.setFixedSize(14, 14)
        btn_max.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_max.clicked.connect(self._toggle_maximize)

        title_row.addWidget(btn_close)
        title_row.addWidget(btn_min)
        title_row.addWidget(btn_max)
        title_row.addSpacing(6)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self._status_label)
        layout.addLayout(title_row)

        # Device dropdown
        self._device_combo = QComboBox()
        self._populate_devices()
        layout.addWidget(self._device_combo)

        # Mic toggle button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._mic_btn = QPushButton("\U0001f3a4")  # mic emoji
        self._mic_btn.setObjectName("mic")
        self._mic_btn.setProperty("recording", False)
        self._mic_btn.clicked.connect(self._toggle_recording)
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(self._mic_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Transcript section
        t_label = QLabel("TRANSCRIPT")
        t_label.setObjectName("section")
        layout.addWidget(t_label)

        self._transcript_label = QLabel("")
        self._transcript_label.setObjectName("transcript")
        self._transcript_label.setWordWrap(True)
        self._transcript_label.setMinimumHeight(60)
        self._transcript_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        t_scroll = QScrollArea()
        t_scroll.setWidgetResizable(True)
        t_scroll.setWidget(self._transcript_label)
        t_scroll.setMaximumHeight(60)
        t_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,30); border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )
        layout.addWidget(t_scroll)

        # Answer section
        a_label = QLabel("ANSWER")
        a_label.setObjectName("section")
        layout.addWidget(a_label)

        self._answer_browser = QTextBrowser()
        self._answer_browser.setObjectName("answer")
        self._answer_browser.setReadOnly(True)
        self._answer_browser.setOpenExternalLinks(False)
        self._answer_browser.setMinimumHeight(180)
        self._answer_browser.setStyleSheet(
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,30); border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )
        layout.addWidget(self._answer_browser, 1)

        # Action buttons
        action_row = QHBoxLayout()
        self._copy_btn = QPushButton("\U0001f4cb Copy")
        self._copy_btn.setObjectName("action")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.clicked.connect(self._copy_answer)
        self._copy_btn.setEnabled(False)

        self._regen_btn = QPushButton("\U0001f504 Regenerate")
        self._regen_btn.setObjectName("action")
        self._regen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._regen_btn.clicked.connect(self._regenerate)
        self._regen_btn.setEnabled(False)

        action_row.addWidget(self._copy_btn)
        action_row.addWidget(self._regen_btn)
        layout.addLayout(action_row)

        # Footer: version + link + resize grip
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(6)

        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: rgba(255,255,255,90); font-size: 10px;")

        sep_label = QLabel("\u00b7")
        sep_label.setStyleSheet("color: rgba(255,255,255,60); font-size: 10px;")

        link_label = QLabel('<a href="https://celox.io" style="color: rgba(52,199,89,180); text-decoration: none; font-size: 10px;">celox.io</a>')
        link_label.setOpenExternalLinks(True)
        link_label.setCursor(Qt.CursorShape.PointingHandCursor)

        grip = QLabel("\u25e2")
        grip.setStyleSheet("color: rgba(255,255,255,20); font-size: 14px;")
        grip.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        footer_row.addWidget(version_label)
        footer_row.addWidget(sep_label)
        footer_row.addWidget(link_label)
        footer_row.addStretch()
        footer_row.addWidget(grip)
        layout.addLayout(footer_row)

        # Position at right side of screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.width() - self.width() - 20,
                (geo.height() - self.height()) // 2,
            )

    def _populate_devices(self):
        self._device_combo.clear()
        self._device_combo.addItem("Default Microphone", None)
        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    name = d["name"]
                    self._device_combo.addItem(f"{name}", i)
        except Exception as e:
            log.warning(f"Could not query audio devices: {e}")

    # -- Worker setup -------------------------------------------------------

    def _init_worker(self):
        self._worker = AsyncWorker()
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)

        # Connect signals
        self._worker.transcript_partial.connect(self._on_transcript_partial)
        self._worker.transcript_final.connect(self._on_transcript_final)
        self._worker.answer_chunk.connect(self._on_answer_chunk)
        self._worker.answer_done.connect(self._on_answer_done)
        self._worker.status_changed.connect(self._on_status_changed)
        self._worker.error_occurred.connect(self._on_error)

        self._thread.start()

    # -- Hotkey -------------------------------------------------------------

    def _init_hotkey(self):
        self._hotkey_monitor = None
        if sys.platform == "darwin":
            self._init_hotkey_macos()
        else:
            self._init_hotkey_pynput()

    def _init_hotkey_macos(self):
        """Use native NSEvent global monitor (avoids pynput crash on macOS 14+)."""
        try:
            from AppKit import NSEvent

            NSKeyDownMask = 1 << 10
            NSCommandKeyMask = 1 << 20
            NSShiftKeyMask = 1 << 17
            R_KEYCODE = 15

            def handler(event):
                flags = event.modifierFlags()
                if (flags & NSCommandKeyMask) and (flags & NSShiftKeyMask) and event.keyCode() == R_KEYCODE:
                    QTimer.singleShot(0, self._toggle_recording)

            self._hotkey_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSKeyDownMask, handler
            )
            log.info("Hotkey registered: Cmd+Shift+R (NSEvent)")
        except Exception as e:
            log.warning(f"Could not register macOS hotkey: {e}")
            self._init_hotkey_pynput()

    def _init_hotkey_pynput(self):
        """Fallback using pynput for non-macOS platforms."""
        try:
            from pynput.keyboard import GlobalHotKeys

            hotkey_str = "<ctrl>+<shift>+r"
            self._hotkey_listener = GlobalHotKeys(
                {hotkey_str: self._hotkey_triggered}
            )
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
            log.info(f"Hotkey registered: {hotkey_str}")
        except Exception as e:
            log.warning(f"Could not register hotkey: {e}")

    def _hotkey_triggered(self):
        QTimer.singleShot(0, self._toggle_recording)

    # -- Pulse animation ----------------------------------------------------

    def _init_pulse_timer(self):
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse_tick)

    def _pulse_tick(self):
        if not self._recording:
            self._pulse_timer.stop()
            return
        self._pulse_on = not self._pulse_on
        if self._pulse_on:
            self._mic_btn.setStyleSheet(
                "QPushButton#mic { background-color: rgba(255, 59, 48, 220); "
                "border-color: rgba(255, 59, 48, 255); }"
            )
        else:
            self._mic_btn.setStyleSheet(
                "QPushButton#mic { background-color: rgba(255, 59, 48, 120); "
                "border-color: rgba(255, 59, 48, 180); }"
            )

    # -- Recording toggle ---------------------------------------------------

    def _toggle_recording(self):
        if self._recording:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._recording = True
        self._mic_btn.setProperty("recording", True)
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)
        self._copy_btn.setEnabled(False)
        self._regen_btn.setEnabled(False)
        self._transcript_label.setText("")
        self._answer_browser.setHtml("")

        device = self._device_combo.currentData()
        self._worker.start_recording(device)
        self._pulse_timer.start(600)

    def _stop(self):
        self._recording = False
        self._pulse_timer.stop()
        self._mic_btn.setProperty("recording", False)
        self._mic_btn.setStyleSheet("")  # Reset custom pulse style
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)
        self._worker.stop_recording()

    # -- Slots --------------------------------------------------------------

    @pyqtSlot(str)
    def _on_transcript_partial(self, text: str):
        self._transcript_label.setText(text)

    @pyqtSlot(str)
    def _on_transcript_final(self, text: str):
        self._transcript_label.setText(text)
        self._last_transcript = text

    @pyqtSlot(str)
    def _on_answer_chunk(self, text: str):
        sb = self._answer_browser.verticalScrollBar()
        pos = sb.value()
        self._answer_browser.setHtml(_markdown_to_html(text))
        sb.setValue(pos)

    @pyqtSlot()
    def _on_answer_done(self):
        self._copy_btn.setEnabled(True)
        self._regen_btn.setEnabled(True)
        # Log session
        if self._last_transcript and self._last_answer:
            self._session_logger.log(self._last_transcript, self._last_answer)

    @pyqtSlot(str)
    def _on_status_changed(self, status: str):
        self._status_label.setText(status)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        log.error(f"Error: {msg}")
        self._status_label.setText("Error")
        # Brief status flash, then reset
        QTimer.singleShot(3000, lambda: self._status_label.setText("Ready"))

    # -- Action buttons -----------------------------------------------------

    def _copy_answer(self):
        if self._last_answer:
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(self._last_answer)
            self._copy_btn.setText("\u2705 Copied!")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("\U0001f4cb Copy"))

    def _regenerate(self):
        self._regen_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)
        self._answer_browser.setHtml("")
        self._worker.regenerate()

    # -- Window controls ----------------------------------------------------

    def _toggle_maximize(self):
        if self._normal_geometry:
            self.setGeometry(self._normal_geometry)
            self._normal_geometry = None
        else:
            self._normal_geometry = self.geometry()
            screen = QGuiApplication.primaryScreen()
            if screen:
                self.setGeometry(screen.availableGeometry())

    # -- Dragging + Resizing ------------------------------------------------

    _RESIZE_MARGIN = 10  # px from bottom-right corner

    def _in_resize_zone(self, pos):
        return (
            pos.x() >= self.width() - self._RESIZE_MARGIN
            and pos.y() >= self.height() - self._RESIZE_MARGIN
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._in_resize_zone(event.position().toPoint()):
                self._resizing = True
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_size = self.size()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            # Update cursor when hovering
            if self._in_resize_zone(event.position().toPoint()):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if getattr(self, "_resizing", False):
            delta = event.globalPosition().toPoint() - self._resize_origin
            new_w = max(self.minimumWidth(), self._resize_size.width() + delta.x())
            new_h = max(self.minimumHeight(), self._resize_size.height() + delta.y())
            self.resize(new_w, new_h)
        elif self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resizing = False

    # -- Cleanup ------------------------------------------------------------

    def closeEvent(self, event):
        log.info("Shutting down...")
        self._worker.shutdown()
        self._thread.quit()
        self._thread.wait(3000)
        try:
            if self._hotkey_monitor:
                from AppKit import NSEvent
                NSEvent.removeMonitor_(self._hotkey_monitor)
            elif hasattr(self, '_hotkey_listener'):
                self._hotkey_listener.stop()
        except Exception:
            pass
        event.accept()


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------


def validate_env():
    missing = []
    if not DEEPGRAM_API_KEY:
        missing.append("DEEPGRAM_API_KEY")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    return missing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("stupidisco")

    # Set app icon
    icon_path = _resource_path("icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    missing = validate_env()
    if missing:
        global DEEPGRAM_API_KEY, ANTHROPIC_API_KEY
        dialog = ApiKeyDialog(missing)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        dialog.save_env()
        env_file = dialog.env_path
        load_dotenv(dotenv_path=env_file, override=True)
        DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
        ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        still_missing = validate_env()
        if still_missing:
            QMessageBox.critical(
                None,
                "stupidisco — API Keys ungültig",
                "Keys konnten nicht gespeichert werden:\n\n"
                + "\n".join(f"  - {k}" for k in still_missing),
            )
            sys.exit(1)

    window = StupidiscoApp()
    window.show()
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
