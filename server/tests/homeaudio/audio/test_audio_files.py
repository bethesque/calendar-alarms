import pytest
from homeaudio.audio.audio_files import AudioFile, AudioFileManager, AudioFileNotFound, AudioLibrary, InvalidAudioFileName, safe_file_name

@pytest.fixture
def directory(tmp_path):
    return tmp_path / "sound_effects"

@pytest.fixture
def manager(directory):
    return AudioFileManager(AudioLibrary("sound-effects", "Sound effects", str(directory), {".mp3"}))

@pytest.mark.parametrize("name", ["../escape.mp3", "a/b.mp3", ".hidden.mp3", "", None, "script.sh", "ding.mp3.disabled"])
def test_safe_file_name_rejects_invalid_names(name):
    with pytest.raises(InvalidAudioFileName):
        safe_file_name(name, {".mp3"})

def test_safe_file_name_accepts_mp3_case_insensitively():
    assert safe_file_name("Ding.MP3", {".mp3"}) == "Ding.MP3"

def test_safe_file_name_uses_given_extensions():
    assert safe_file_name("ding.wav", {".mp3", ".wav"}) == "ding.wav"
    with pytest.raises(InvalidAudioFileName):
        safe_file_name("ding.mp3", {".wav"})

def test_list_files_when_directory_missing(manager):
    assert not manager.directory_exists()
    assert manager.list_files() == []

def test_list_files_includes_enabled_and_disabled_mp3s_sorted(manager, directory):
    directory.mkdir()
    (directory / "b.mp3").write_bytes(b"12")
    (directory / "A.mp3.disabled").write_bytes(b"1")
    (directory / "notes.txt").write_text("nope")
    (directory / "notes.txt.disabled").write_text("nope")

    assert manager.list_files() == [AudioFile("A.mp3", False, 1), AudioFile("b.mp3", True, 2)]

def test_save_creates_directory_and_replaces_disabled_copy(manager, directory):
    directory.mkdir()
    (directory / "ding.mp3.disabled").write_bytes(b"old")

    assert manager.save([("ding.mp3", b"new"), ("dong.mp3", b"two")]) == ["ding.mp3", "dong.mp3"]
    assert (directory / "ding.mp3").read_bytes() == b"new"
    assert (directory / "dong.mp3").read_bytes() == b"two"
    assert not (directory / "ding.mp3.disabled").exists()

def test_save_writes_nothing_when_any_name_is_invalid(manager, directory):
    with pytest.raises(InvalidAudioFileName):
        manager.save([("ding.mp3", b"one"), ("evil.sh", b"rm")])

    assert not directory.exists()

def test_existing_path_prefers_enabled_then_disabled(manager, directory):
    directory.mkdir()
    (directory / "ding.mp3.disabled").write_bytes(b"abc")

    assert manager.existing_path("ding.mp3") == directory / "ding.mp3.disabled"

    (directory / "ding.mp3").write_bytes(b"abc")

    assert manager.existing_path("ding.mp3") == directory / "ding.mp3"

def test_existing_path_raises_when_missing(manager):
    with pytest.raises(AudioFileNotFound):
        manager.existing_path("missing.mp3")

def test_toggle_disables_then_enables(manager, directory):
    directory.mkdir()
    (directory / "ding.mp3").write_bytes(b"abc")

    assert manager.toggle("ding.mp3") is False
    assert [f.name for f in directory.iterdir()] == ["ding.mp3.disabled"]

    assert manager.toggle("ding.mp3") is True
    assert [f.name for f in directory.iterdir()] == ["ding.mp3"]

def test_delete_removes_disabled_file(manager, directory):
    directory.mkdir()
    (directory / "ding.mp3.disabled").write_bytes(b"abc")

    manager.delete("ding.mp3")

    assert list(directory.iterdir()) == []
