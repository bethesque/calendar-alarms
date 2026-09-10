import os

import pytest

from homeaudio.vcal.event_notifications import text_to_voice as text_to_voice_module
from homeaudio.vcal.event_notifications.text_to_voice import (
    TextToSpeechError,
    text_to_voice_file,
)


class FakeGTTS:
    """Stand-in for gTTS.gTTS - records the text it was asked to speak and, on save(),
    replays the next canned behaviour from `behaviours` (either bytes to write, or an
    exception instance to raise)."""

    calls = []

    def __init__(self, text, timeout, lang, tld):
        self.text = text
        type(self).calls.append(text)

    def save(self, file_path):
        behaviour = type(self).behaviours.pop(0)
        if isinstance(behaviour, Exception):
            raise behaviour
        with open(file_path, "wb") as f:
            f.write(behaviour)


def _install_fake_gtts(monkeypatch, behaviours):
    FakeGTTS.calls = []
    FakeGTTS.behaviours = list(behaviours)
    monkeypatch.setattr(text_to_voice_module, "gTTS", FakeGTTS)
    monkeypatch.setattr(text_to_voice_module, "TTS_RETRY_DELAY_SECONDS", 0)
    return FakeGTTS


def test_returns_existing_cached_file_without_calling_gtts(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[])
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    expected_path = text_to_voice_module.get_file_path_for_text(
        "Hello there", text_to_voice_module.gtts_tld(), str(cache_dir)
    )
    os.makedirs(os.path.dirname(expected_path), exist_ok=True)
    with open(expected_path, "wb") as f:
        f.write(b"already generated audio")

    result = text_to_voice_file("Hello there", audio_cache_directory=str(cache_dir))

    assert result == expected_path
    assert FakeGTTS.calls == []


def test_regenerates_when_cached_file_is_empty(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    expected_path = text_to_voice_module.get_file_path_for_text(
        "Hello there", text_to_voice_module.gtts_tld(), str(cache_dir)
    )
    open(expected_path, "wb").close()  # simulate a corrupted, zero-length cache entry

    result = text_to_voice_file("Hello there", audio_cache_directory=str(cache_dir))

    assert result == expected_path
    assert os.path.getsize(result) == len(b"real audio bytes")
    assert not os.path.exists(expected_path + ".tmp")


def test_writes_new_file_on_first_success(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    cache_dir = tmp_path / "audio"

    result = text_to_voice_file("Hello there", audio_cache_directory=str(cache_dir))

    assert os.path.exists(result)
    with open(result, "rb") as f:
        assert f.read() == b"real audio bytes"
    assert not os.path.exists(result + ".tmp")
    assert FakeGTTS.calls == ["Hello there"]


def test_retries_after_empty_file_then_succeeds(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"", b"real audio bytes"])
    cache_dir = tmp_path / "audio"

    result = text_to_voice_file("Hello there", audio_cache_directory=str(cache_dir))

    assert os.path.getsize(result) == len(b"real audio bytes")
    assert len(FakeGTTS.calls) == 2


def test_retries_after_exception_then_succeeds(monkeypatch, tmp_path):
    _install_fake_gtts(
        monkeypatch, behaviours=[ConnectionError("network blip"), b"real audio bytes"]
    )
    cache_dir = tmp_path / "audio"

    result = text_to_voice_file("Hello there", audio_cache_directory=str(cache_dir))

    assert os.path.getsize(result) == len(b"real audio bytes")
    assert len(FakeGTTS.calls) == 2


def test_raises_text_to_speech_error_after_exhausting_all_attempts(monkeypatch, tmp_path):
    _install_fake_gtts(
        monkeypatch,
        behaviours=[
            ConnectionError("network blip"),
            b"",
            ConnectionError("network blip again"),
        ],
    )
    cache_dir = tmp_path / "audio"
    expected_path = text_to_voice_module.get_file_path_for_text(
        "Hello there", text_to_voice_module.gtts_tld(), str(cache_dir)
    )

    with pytest.raises(TextToSpeechError):
        text_to_voice_file("Hello there", audio_cache_directory=str(cache_dir))

    assert len(FakeGTTS.calls) == text_to_voice_module.TTS_MAX_ATTEMPTS
    assert not os.path.exists(expected_path)
    assert not os.path.exists(expected_path + ".tmp")


def test_truncates_text_to_word_limit_before_generating(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    cache_dir = tmp_path / "audio"

    text_to_voice_file(
        "one two three four five", word_limit=3, audio_cache_directory=str(cache_dir)
    )

    assert FakeGTTS.calls == ["one two three"]
