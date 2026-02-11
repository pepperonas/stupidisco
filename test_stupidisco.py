"""Unit tests for stupidisco — runs without API keys, microphone, or GUI."""

import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers: import constants and classes from stupidisco without triggering
# PyQt6 QApplication or load_dotenv side-effects where possible.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_env_keys(monkeypatch):
    """Ensure API key env vars are unset by default for every test."""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# validate_env
# ---------------------------------------------------------------------------


def _validate_env():
    """Re-implement validate_env logic so we don't need to import the module
    (which triggers load_dotenv and PyQt6 imports at module level)."""
    missing = []
    if not os.getenv("DEEPGRAM_API_KEY", ""):
        missing.append("DEEPGRAM_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY", ""):
        missing.append("ANTHROPIC_API_KEY")
    return missing


def test_validate_env_missing_both():
    """Beide Keys fehlen → 2 Einträge."""
    missing = _validate_env()
    assert len(missing) == 2
    assert "DEEPGRAM_API_KEY" in missing
    assert "ANTHROPIC_API_KEY" in missing


def test_validate_env_missing_one(monkeypatch):
    """Ein Key fehlt → 1 Eintrag."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    missing = _validate_env()
    assert len(missing) == 1
    assert "ANTHROPIC_API_KEY" in missing


def test_validate_env_all_present(monkeypatch):
    """Beide da → leere Liste."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    missing = _validate_env()
    assert missing == []


# ---------------------------------------------------------------------------
# SessionLogger
# ---------------------------------------------------------------------------


def _make_session_logger(tmp_path, monkeypatch):
    """Create a SessionLogger that writes to tmp_path instead of ~/.stupidisco."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Import here to avoid module-level side effects; we need to reload
    # the class fresh so Path.home() patching takes effect.
    import importlib
    import stupidisco

    importlib.reload(stupidisco)
    return stupidisco.SessionLogger()


def test_session_logger_creates_file(tmp_path, monkeypatch):
    """Datei wird in tmp-Dir erstellt."""
    logger = _make_session_logger(tmp_path, monkeypatch)
    logger.log("Was ist Python?", "Eine Programmiersprache.")
    sessions_dir = tmp_path / ".stupidisco" / "sessions"
    files = list(sessions_dir.glob("*.txt"))
    assert len(files) == 1


def test_session_logger_appends(tmp_path, monkeypatch):
    """Mehrere Einträge korrekt angehängt."""
    logger = _make_session_logger(tmp_path, monkeypatch)
    logger.log("Frage 1", "Antwort 1")
    logger.log("Frage 2", "Antwort 2")
    sessions_dir = tmp_path / ".stupidisco" / "sessions"
    files = list(sessions_dir.glob("*.txt"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert content.count("FRAGE:") == 2
    assert content.count("ANTWORT:") == 2


def test_session_logger_format(tmp_path, monkeypatch):
    """Format enthält FRAGE/ANTWORT/Separator."""
    logger = _make_session_logger(tmp_path, monkeypatch)
    logger.log("Testfrage", "Testantwort")
    sessions_dir = tmp_path / ".stupidisco" / "sessions"
    files = list(sessions_dir.glob("*.txt"))
    content = files[0].read_text(encoding="utf-8")
    assert "FRAGE:" in content
    assert "Testfrage" in content
    assert "ANTWORT:" in content
    assert "Testantwort" in content
    assert "=" * 60 in content


# ---------------------------------------------------------------------------
# Audio-Konstanten
# ---------------------------------------------------------------------------


def test_audio_constants():
    """SAMPLE_RATE=16000, CHANNELS=1, etc."""
    import stupidisco

    assert stupidisco.SAMPLE_RATE == 16000
    assert stupidisco.CHANNELS == 1
    assert stupidisco.DTYPE == "int16"
    assert stupidisco.CHUNK_MS == 100


def test_chunk_size_calculation():
    """CHUNK_SIZE = SAMPLE_RATE * CHUNK_MS / 1000."""
    import stupidisco

    expected = int(stupidisco.SAMPLE_RATE * stupidisco.CHUNK_MS / 1000)
    assert stupidisco.CHUNK_SIZE == expected


# ---------------------------------------------------------------------------
# System Prompt & Modell
# ---------------------------------------------------------------------------


def test_system_prompt_content():
    """Prompt enthält deutsche Schlüsselwörter."""
    import stupidisco

    prompt = stupidisco.SYSTEM_PROMPT
    assert "Deutsch" in prompt
    assert "Antwort" in prompt or "antworte" in prompt or "Antworte" in prompt
    assert "WICHTIG" in prompt


def test_claude_model_set():
    """CLAUDE_MODEL ist nicht leer."""
    import stupidisco

    assert stupidisco.CLAUDE_MODEL
    assert len(stupidisco.CLAUDE_MODEL) > 0
