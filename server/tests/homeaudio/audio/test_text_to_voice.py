import os

import pytest
from gtts import gTTSError

from homeaudio.audio import text_to_voice as text_to_voice_module
from homeaudio.audio.settings import GoogleTextToSpeechSettings
from homeaudio.audio.text_to_voice import (
    gtts_speed,
    TextToSpeechError,
    TextToSpeechRateLimitError,
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
    monkeypatch.setattr(text_to_voice_module, "gtts_tld", lambda settings=None: "com")
    return FakeGTTS


def test_returns_existing_cached_file_without_calling_gtts(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[])
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    expected_path = text_to_voice_module._get_file_path_for_text(
        "Hello there", text_to_voice_module.gtts_tld(), str(cache_dir)
    )
    os.makedirs(os.path.dirname(expected_path), exist_ok=True)
    with open(expected_path, "wb") as f:
        f.write(b"already generated audio")

    result = text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert result == expected_path
    assert FakeGTTS.calls == []


def test_regenerates_when_cached_file_is_empty(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    expected_path = text_to_voice_module._get_file_path_for_text(
        "Hello there", text_to_voice_module.gtts_tld(), str(cache_dir)
    )
    open(expected_path, "wb").close()  # simulate a corrupted, zero-length cache entry

    result = text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert result == expected_path
    assert os.path.getsize(result) == len(b"real audio bytes")
    assert not os.path.exists(expected_path + ".tmp")


def test_writes_new_file_on_first_success(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    cache_dir = tmp_path / "audio"

    result = text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert os.path.exists(result)
    with open(result, "rb") as f:
        assert f.read() == b"real audio bytes"
    assert not os.path.exists(result + ".tmp")
    assert FakeGTTS.calls == ["Hello there"]


def test_retries_after_empty_file_then_succeeds(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"", b"real audio bytes"])
    cache_dir = tmp_path / "audio"

    result = text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert os.path.getsize(result) == len(b"real audio bytes")
    assert len(FakeGTTS.calls) == 2


def test_retries_after_exception_then_succeeds(monkeypatch, tmp_path):
    _install_fake_gtts(
        monkeypatch, behaviours=[ConnectionError("network blip"), b"real audio bytes"]
    )
    cache_dir = tmp_path / "audio"

    result = text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

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
    expected_path = text_to_voice_module._get_file_path_for_text(
        "Hello there", text_to_voice_module.gtts_tld(), str(cache_dir)
    )

    with pytest.raises(TextToSpeechError):
        text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert len(FakeGTTS.calls) == text_to_voice_module.TTS_MAX_ATTEMPTS
    assert not os.path.exists(expected_path)
    assert not os.path.exists(expected_path + ".tmp")


def test_truncates_text_to_word_limit_before_generating(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    cache_dir = tmp_path / "audio"

    text_to_voice_file(
        "one two three four five", word_limit=3, speed=1.0, audio_cache_directory=str(cache_dir)
    )

    assert FakeGTTS.calls == ["one two three"]


class FakeResponse:
    def __init__(self, status_code, reason):
        self.status_code = status_code
        self.reason = reason


def test_raises_rate_limit_error_without_retrying_on_429(monkeypatch, tmp_path):
    _install_fake_gtts(
        monkeypatch,
        behaviours=[gTTSError(response=FakeResponse(429, "Too Many Requests")), b"real audio bytes"],
    )
    cache_dir = tmp_path / "audio"

    with pytest.raises(TextToSpeechRateLimitError):
        text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert len(FakeGTTS.calls) == 1


def test_retries_after_non_rate_limit_gtts_error(monkeypatch, tmp_path):
    _install_fake_gtts(
        monkeypatch,
        behaviours=[gTTSError(response=FakeResponse(500, "Internal Server Error")), b"real audio bytes"],
    )
    cache_dir = tmp_path / "audio"

    result = text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert os.path.getsize(result) == len(b"real audio bytes")
    assert len(FakeGTTS.calls) == 2


def _install_fake_change_speed(monkeypatch):
    calls = []

    def fake_change_speed(input_file, output_file, speed):
        calls.append((input_file, output_file, speed))
        with open(output_file, "wb") as f:
            f.write(b"sped up audio")
        return output_file

    monkeypatch.setattr(text_to_voice_module, "change_speed", fake_change_speed)
    return calls


def _original_and_sped_up_paths(cache_dir):
    original = text_to_voice_module._get_file_path_for_text("Hello there", "com", str(cache_dir))
    return original, original[: -len(".mp3")] + ".speed_1_5.wav"


def test_downloads_then_changes_speed(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    change_speed_calls = _install_fake_change_speed(monkeypatch)
    cache_dir = tmp_path / "audio"
    original, sped_up = _original_and_sped_up_paths(cache_dir)

    result = text_to_voice_file("Hello there", speed=1.5, audio_cache_directory=str(cache_dir))

    assert result == sped_up
    assert change_speed_calls == [(original, sped_up, 1.5)]
    with open(original, "rb") as f:
        assert f.read() == b"real audio bytes"


def test_changes_speed_of_cached_original_without_calling_gtts(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[])
    change_speed_calls = _install_fake_change_speed(monkeypatch)
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    original, sped_up = _original_and_sped_up_paths(cache_dir)
    with open(original, "wb") as f:
        f.write(b"already generated audio")

    result = text_to_voice_file("Hello there", speed=1.5, audio_cache_directory=str(cache_dir))

    assert result == sped_up
    assert FakeGTTS.calls == []
    assert change_speed_calls == [(original, sped_up, 1.5)]


def test_returns_cached_sped_up_file_without_calling_gtts_or_changing_speed(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[])
    change_speed_calls = _install_fake_change_speed(monkeypatch)
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    _, sped_up = _original_and_sped_up_paths(cache_dir)
    with open(sped_up, "wb") as f:
        f.write(b"already sped up audio")

    result = text_to_voice_file("Hello there", speed=1.5, audio_cache_directory=str(cache_dir))

    assert result == sped_up
    assert FakeGTTS.calls == []
    assert change_speed_calls == []


def test_does_not_change_speed_when_speed_is_one(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])
    change_speed_calls = _install_fake_change_speed(monkeypatch)
    cache_dir = tmp_path / "audio"
    original, _ = _original_and_sped_up_paths(cache_dir)

    result = text_to_voice_file("Hello there", speed=1.0, audio_cache_directory=str(cache_dir))

    assert result == original
    assert change_speed_calls == []


def test_returns_original_file_when_changing_speed_fails(monkeypatch, tmp_path):
    _install_fake_gtts(monkeypatch, behaviours=[b"real audio bytes"])

    def failing_change_speed(input_file, output_file, speed):
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr(text_to_voice_module, "change_speed", failing_change_speed)
    cache_dir = tmp_path / "audio"
    original, sped_up = _original_and_sped_up_paths(cache_dir)

    result = text_to_voice_file("Hello there", speed=1.5, audio_cache_directory=str(cache_dir))

    assert result == original
    assert not os.path.exists(sped_up)


def _install_fake_select_option(monkeypatch, result):
    calls = []

    def fake_select_option_pseudorandomly(default_text, threshold, options_source):
        calls.append((default_text, threshold, options_source.get_options()))
        return result

    monkeypatch.setattr(text_to_voice_module, "select_option_pseudorandomly", fake_select_option_pseudorandomly)
    return calls


def _speed_settings():
    return GoogleTextToSpeechSettings(default_speed=1.1, alternative_speeds=[1.0, 1.25], alternative_speed_probability=0.4)


def test_gtts_speed_selects_from_alternative_speeds_as_strings(monkeypatch):
    calls = _install_fake_select_option(monkeypatch, result="1.1")

    gtts_speed(_speed_settings())

    assert calls == [("1.1", 0.4, ["1.0", "1.25"])]


def test_gtts_speed_returns_selected_speed_as_float(monkeypatch):
    _install_fake_select_option(monkeypatch, result="1.25")

    assert gtts_speed(_speed_settings()) == 1.25


def test_gtts_speed_returns_default_speed_when_nothing_selected(monkeypatch):
    _install_fake_select_option(monkeypatch, result=None)

    assert gtts_speed(_speed_settings()) == 1.1
