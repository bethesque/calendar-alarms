import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import vcal.announcements.announce as announce_module
from vcal.scene import NullScene


def test_play_audio_file_as_announcement_uses_snapserver_and_mpd(monkeypatch):
    mock_mpd_client = Mock()
    mock_snapserver = Mock()
    mock_snapserver.connected_client_names.return_value = ["livingroom"]
    mock_snapserver.set_volumes.return_value = None

    @contextmanager
    def fake_mpd_connection():
        yield mock_mpd_client

    mock_snapcast_settings = Mock()
    mock_snapcast_settings.snapserver_rpc_url.return_value = "http://snapserver"
    mock_snapcast_settings.volumes_for_players.return_value = {"livingroom": 80}
    mock_snapcast_settings.snapclients = []

    mock_mpd_settings = Mock()
    mock_mpd_settings.volumes = {"talkie": 25}

    monkeypatch.setattr(announce_module, "normalize_audio", lambda *args, **kwargs: None)
    monkeypatch.setattr(announce_module, "get_pre_announcement_files", lambda sound_effect=None: [])
    monkeypatch.setattr(announce_module, "track_length", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(announce_module.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(announce_module, "mpd_connection", fake_mpd_connection)
    monkeypatch.setattr(announce_module, "Snapserver", Mock(return_value=mock_snapserver))
    monkeypatch.setattr(announce_module, "SnapcastSettings", Mock(return_value=mock_snapcast_settings))
    monkeypatch.setattr(announce_module, "MpdSettings", Mock(return_value=mock_mpd_settings))

    announce_module.play_audio_file_as_announcement(
        "/tmp/demo.mp3",
        NullScene(),
        sound_effect=None,
    )

    mock_snapserver.connected_client_names.assert_called_once_with()
    mock_snapserver.set_volumes.assert_called_once_with({"livingroom": 80})
    mock_mpd_client.set_volume.assert_called_once_with(25)
    mock_mpd_client.play_files.assert_called_once()


def test_morning_announcements_builder_builds_audio_file(monkeypatch):
    builder = announce_module.MorningAnnouncementsBuilder()
    recorded = {}

    def fake_mix(*, speech_file, music_file, output_file):
        recorded["speech_file"] = speech_file
        recorded["music_file"] = music_file
        recorded["output_file"] = output_file

    monkeypatch.setattr(announce_module, "mix_announcement_audio", fake_mix)
    monkeypatch.setattr(
        builder,
        "get_morning_announcements_speech_file",
        lambda calendar_file, base_time: "/tmp/generated_speech.mp3",
    )

    result = builder.build_audio_file(
        calendar_file="/tmp/calendar.json",
        base_time=None,
        background_music_file="/tmp/music.mp3",
    )

    assert result == announce_module.MORNING_ANNOUNCEMENTS_AUDIO_FILE
    assert recorded == {
        "speech_file": "/tmp/generated_speech.mp3",
        "music_file": "/tmp/music.mp3",
        "output_file": announce_module.MORNING_ANNOUNCEMENTS_AUDIO_FILE,
    }
