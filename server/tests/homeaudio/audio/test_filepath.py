import pytest

from homeaudio.audio.filepath import insert_path_part, modify_path


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/a/speech.mp3", "/a/speech.fast.mp3"),
        ("/a/speech.22050.mono.wav", "/a/speech.fast.22050.mono.wav"),
        ("/a/speech", "/a/speech.fast"),
        ("speech.wav", "speech.fast.wav"),
        ("/a/b.c/speech.wav", "/a/b.c/speech.fast.wav"),
    ],
)
def test_insert_path_part(path, expected):
    assert insert_path_part(path, "fast") == expected


def test_modify_path_with_no_changes():
    assert modify_path("/a/speech.mono.wav") == "/a/speech.mono.wav"


def test_modify_path_changes_directory():
    assert modify_path("/a/speech.mono.wav", directory="/cache") == "/cache/speech.mono.wav"


def test_modify_path_changes_last_suffix():
    assert modify_path("/a/speech.mono.wav", suffix=".mp3") == "/a/speech.mono.mp3"


def test_modify_path_accepts_suffix_without_dot():
    assert modify_path("/a/speech.mono.wav", suffix="mp3") == "/a/speech.mono.mp3"


def test_modify_path_inserts_part():
    assert modify_path("/a/speech.mono.wav", part="fast") == "/a/speech.fast.mono.wav"


def test_modify_path_with_all_changes():
    assert (
        modify_path("/a/speech.mono.wav", directory="/cache", suffix="mp3", part="fast")
        == "/cache/speech.fast.mono.mp3"
    )


def test_modify_path_adds_suffix_when_there_is_none():
    assert modify_path("/a/speech", suffix="wav", part="fast") == "/a/speech.fast.wav"
