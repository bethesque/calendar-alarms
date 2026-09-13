import pytest

from homeaudio.vcal.event_notifications import AUDIO_DIRECTORY
from homeaudio.audio.wav import AUDIO_CACHE_DIR, get_wav_cache_file_path


def test_get_wav_cache_file_path_for_file_in_audio_directory():
    not_wav = AUDIO_DIRECTORY / "bar" / "foo.mp3"

    result = get_wav_cache_file_path(str(not_wav))

    assert result == str(AUDIO_CACHE_DIR / "audio_resources" / "bar" / "foo.wav")


def test_get_wav_cache_file_path_for_file_in_audio_cache_dir():
    not_wav = AUDIO_CACHE_DIR / "foo" / "bar.mp3"

    result = get_wav_cache_file_path(str(not_wav))

    assert result == f"{AUDIO_CACHE_DIR}/foo/bar.wav"


def test_get_wav_cache_file_path_raises_for_unknown_directory():
    with pytest.raises(RuntimeError):
        get_wav_cache_file_path("/some/other/place/baz.mp3")
