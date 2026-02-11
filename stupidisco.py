#!/usr/bin/env python3
"""
stupidisco — Real-time Interview Assistant Overlay for macOS

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

import asyncio
import logging
import os
import sys
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
)
from PyQt6.QtGui import QFont, QIcon, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

CLAUDE_MODEL = "claude-3-5-haiku-20241022"
SYSTEM_PROMPT = (
    "Du bist ein extrem präziser, eloquenter Interview-Partner. "
    "Du erhältst ein Live-Transkript (Mikrofonaufnahme) mit möglichen "
    "Fragmenten/Echo. Extrahiere die zuletzt gestellte relevante Frage "
    "und beantworte sie auf Deutsch kompakt in maximal 2–3 Sätzen. "
    "Sei direkt, klar und faktenbasiert. Keine Vorrede, keine Meta-Kommentare."
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
        self._audio_queue: asyncio.Queue | None = None
        self._stream: sd.RawInputStream | None = None
        self._dg_connection = None
        self._recording = False
        self._accumulated_transcript = ""
        self._last_transcript = ""
        self._stop_time: float = 0

    # -- Thread entry point --------------------------------------------------

    def run(self):
        """Called when the QThread starts. Creates and runs the asyncio loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._audio_queue = asyncio.Queue()
        log.info("AsyncWorker event loop running")
        self._loop.run_forever()

    def schedule(self, coro):
        """Schedule a coroutine on the worker's event loop from any thread."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    # -- Recording control ---------------------------------------------------

    def start_recording(self, device_index: int | None):
        self.schedule(self._start_recording(device_index))

    def stop_recording(self):
        self.schedule(self._stop_recording())

    def regenerate(self):
        if self._last_transcript:
            self.schedule(self._generate_answer(self._last_transcript))

    async def _start_recording(self, device_index: int | None):
        if self._recording:
            return
        self._recording = True
        self._accumulated_transcript = ""
        self.status_changed.emit("Recording...")

        try:
            await self._open_deepgram()
            self._open_audio_stream(device_index)
            # Pump audio to Deepgram
            asyncio.ensure_future(self._audio_pump(), loop=self._loop)
        except Exception as e:
            log.exception("Failed to start recording")
            self.error_occurred.emit(f"Recording error: {e}")
            self._recording = False
            self.status_changed.emit("Ready")

    async def _stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        self._stop_time = time.time()
        self.status_changed.emit("Thinking...")

        # Stop audio
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        # Finalize Deepgram
        if self._dg_connection:
            try:
                self._dg_connection.finish()
            except Exception:
                pass
            self._dg_connection = None

        # Wait briefly for any final transcript callbacks
        await asyncio.sleep(0.3)

        transcript = self._accumulated_transcript.strip()
        if not transcript:
            self.status_changed.emit("Ready")
            self.error_occurred.emit("No speech detected. Try again.")
            return

        self._last_transcript = transcript
        self.transcript_final.emit(transcript)
        await self._generate_answer(transcript)

    # -- Deepgram -----------------------------------------------------------

    async def _open_deepgram(self):
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

        dg = DeepgramClient(DEEPGRAM_API_KEY)
        connection = dg.listen.websocket.v("1")

        def on_transcript(_, result, **kwargs):
            try:
                alt = result.channel.alternatives[0]
                text = alt.transcript
                if not text:
                    return
                if result.is_final:
                    self._accumulated_transcript += text + " "
                    self.transcript_final.emit(self._accumulated_transcript.strip())
                else:
                    partial = self._accumulated_transcript + text
                    self.transcript_partial.emit(partial.strip())
            except Exception as e:
                log.warning(f"Transcript parse error: {e}")

        def on_error(_, error, **kwargs):
            log.error(f"Deepgram error: {error}")
            self.error_occurred.emit(f"Deepgram: {error}")

        connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        connection.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            model="nova-3",
            language="de",
            encoding="linear16",
            sample_rate=SAMPLE_RATE,
            channels=CHANNELS,
            interim_results=True,
            smart_format=True,
        )
        connection.start(options)
        self._dg_connection = connection
        log.info("Deepgram connection opened")

    # -- Audio stream -------------------------------------------------------

    def _open_audio_stream(self, device_index: int | None):
        def callback(indata, frames, time_info, status):
            if status:
                log.warning(f"Audio status: {status}")
            if self._recording and self._loop:
                data = bytes(indata)
                self._loop.call_soon_threadsafe(self._audio_queue.put_nowait, data)

        kwargs = dict(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            dtype=DTYPE,
            channels=CHANNELS,
            callback=callback,
        )
        if device_index is not None:
            kwargs["device"] = device_index

        self._stream = sd.RawInputStream(**kwargs)
        self._stream.start()
        log.info(f"Audio stream opened (device={device_index})")

    async def _audio_pump(self):
        """Reads audio from queue and sends to Deepgram."""
        while self._recording and self._dg_connection:
            try:
                data = await asyncio.wait_for(self._audio_queue.get(), timeout=0.2)
                self._dg_connection.send(data)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if self._recording:
                    log.warning(f"Audio pump error: {e}")
                break

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
                max_tokens=300,
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
        if self._recording:
            self._recording = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
            if self._dg_connection:
                try:
                    self._dg_connection.finish()
                except Exception:
                    pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)


# ---------------------------------------------------------------------------
# Main Window — PyQt6 GUI
# ---------------------------------------------------------------------------

STYLESHEET = """
QMainWindow {
    background-color: rgba(24, 24, 28, 230);
    border: 1px solid rgba(255, 255, 255, 30);
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
QLabel#answer {
    font-size: 13px;
    color: #34c759;
    padding: 6px;
    background-color: rgba(52, 199, 89, 10);
    border-radius: 6px;
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
"""


class StupidiscoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self._recording = False
        self._drag_pos: QPoint | None = None
        self._last_answer = ""
        self._last_transcript = ""
        self._pulse_on = False
        self._session_logger = SessionLogger()

        self._init_ui()
        self._init_worker()
        self._init_hotkey()
        self._init_pulse_timer()

    # -- UI -----------------------------------------------------------------

    def _init_ui(self):
        self.setWindowTitle("stupidisco")
        self.setFixedSize(320, 460)
        self.setStyleSheet(STYLESHEET)

        # Frameless, translucent, always-on-top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Title bar
        title_row = QHBoxLayout()
        title = QLabel("stupidisco")
        title.setObjectName("title")
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("status")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
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
        t_scroll.setMaximumHeight(90)
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

        self._answer_label = QLabel("")
        self._answer_label.setObjectName("answer")
        self._answer_label.setWordWrap(True)
        self._answer_label.setMinimumHeight(60)
        self._answer_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        a_scroll = QScrollArea()
        a_scroll.setWidgetResizable(True)
        a_scroll.setWidget(self._answer_label)
        a_scroll.setMaximumHeight(120)
        a_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,30); border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )
        layout.addWidget(a_scroll)

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

        layout.addStretch()

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
        try:
            from pynput.keyboard import GlobalHotKeys

            if sys.platform == "darwin":
                hotkey_str = "<cmd>+<shift>+r"
            else:
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
        # pynput callback runs in a different thread — use QTimer for thread safety
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
        self._answer_label.setText("")

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
        self._answer_label.setText(text)
        self._last_answer = text

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
        self._answer_label.setText("")
        self._worker.regenerate()

    # -- Dragging -----------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # -- Cleanup ------------------------------------------------------------

    def closeEvent(self, event):
        log.info("Shutting down...")
        self._worker.shutdown()
        self._thread.quit()
        self._thread.wait(3000)
        try:
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

    missing = validate_env()
    if missing:
        QMessageBox.critical(
            None,
            "stupidisco — Missing API Keys",
            "Missing environment variables:\n\n"
            + "\n".join(f"  - {k}" for k in missing)
            + "\n\nCreate a .env file with your API keys.\n"
            "See .env.example for details.",
        )
        sys.exit(1)

    window = StupidiscoApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
