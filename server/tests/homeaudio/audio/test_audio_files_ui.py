import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from homeaudio.audio.audio_files import AudioLibrary
from homeaudio.audio.audio_files_ui import AudioFilesRoutes

@pytest.fixture
def sound_effects_dir(tmp_path):
    directory = tmp_path / "sound_effects"
    directory.mkdir()
    return directory

@pytest.fixture
def wake_up_dir(tmp_path):
    return tmp_path / "alarms_wakeup"

@pytest.fixture
def client(sound_effects_dir, wake_up_dir):
    app = FastAPI()
    libraries = [
        AudioLibrary("sound-effects", "Sound effects", str(sound_effects_dir), {".mp3"}),
        AudioLibrary("wake-up-alarms", "Wake up alarms", str(wake_up_dir), {".mp3"}),
    ]
    app.include_router(AudioFilesRoutes(libraries).router, prefix="/admin")
    return TestClient(app)

def test_index_redirects_to_first_library(client):
    response = client.get("/admin/audio-files", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/admin/audio-files/sound-effects")

def test_renders_enabled_and_disabled_files(client, sound_effects_dir):
    (sound_effects_dir / "ding dong.mp3").write_bytes(b"abc")
    (sound_effects_dir / "bell.mp3.disabled").write_bytes(b"abc")

    response = client.get("/admin/audio-files/sound-effects")

    assert response.status_code == 200
    assert "/admin/audio-files/sound-effects/ding%20dong.mp3" in response.text
    assert '<tr class="disabled">' in response.text
    assert ">Enable</button>" in response.text
    assert ">Disable</button>" in response.text

def test_shows_error_when_directory_missing(client):
    response = client.get("/admin/audio-files/wake-up-alarms")

    assert response.status_code == 200
    assert "does not exist" in response.text

def test_unknown_library_is_404(client):
    assert client.get("/admin/audio-files/nope").status_code == 404

def test_upload_saves_files(client, wake_up_dir):
    response = client.post(
        "/admin/audio-files/wake-up-alarms",
        files=[("files", ("a.mp3", b"one", "audio/mpeg")), ("files", ("b.mp3", b"two", "audio/mpeg"))],
    )

    assert response.json() == {"uploaded": ["a.mp3", "b.mp3"]}
    assert (wake_up_dir / "a.mp3").read_bytes() == b"one"

def test_upload_invalid_name_is_400(client):
    response = client.post("/admin/audio-files/sound-effects", files=[("files", ("evil.sh", b"rm", "text/plain"))])

    assert response.status_code == 400

def test_get_file_serves_contents_as_mp3(client, sound_effects_dir):
    (sound_effects_dir / "ding.mp3.disabled").write_bytes(b"abc")

    response = client.get("/admin/audio-files/sound-effects/ding.mp3")

    assert response.content == b"abc"
    assert response.headers["content-type"] == "audio/mpeg"

def test_get_missing_file_is_404(client):
    assert client.get("/admin/audio-files/sound-effects/missing.mp3").status_code == 404

def test_delete_file(client, sound_effects_dir):
    (sound_effects_dir / "ding.mp3").write_bytes(b"abc")

    response = client.delete("/admin/audio-files/sound-effects/ding.mp3")

    assert response.json() == {"deleted": "ding.mp3"}
    assert not (sound_effects_dir / "ding.mp3").exists()

def test_delete_missing_file_is_404(client):
    assert client.delete("/admin/audio-files/sound-effects/missing.mp3").status_code == 404

def test_toggle_file(client, sound_effects_dir):
    (sound_effects_dir / "ding.mp3").write_bytes(b"abc")

    response = client.post("/admin/audio-files/sound-effects/ding.mp3/toggle")

    assert response.json() == {"name": "ding.mp3", "enabled": False}
    assert (sound_effects_dir / "ding.mp3.disabled").exists()

def test_toggle_missing_file_is_404(client):
    assert client.post("/admin/audio-files/sound-effects/missing.mp3/toggle").status_code == 404
