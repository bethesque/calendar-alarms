from contextlib import contextmanager
from datetime import datetime

from homeaudio.vcal.notifications.core import check_for_notifications
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.audio.scene import NullScene
from homeaudio.audio.settings import EventNotificationSettings


class StubSnapserverManager:
    def __init__(self, *args, **kwargs):
        pass

    def connected_player_areas(self):
        return set()

    def set_volumes(self, usecase):
        return set()


class StubMpdPlayer:
    def __init__(self):
        self.play_file_calls = []

    def set_volume(self, volume):
        pass

    def play_file(self, file_path):
        self.play_file_calls.append(file_path)


def test_check_for_notifications_with_announce_event_plays_via_mpd(monkeypatch):
    date_string = "2026-04-06T08:00:00+10:00"
    base_time = datetime.fromisoformat(date_string)

    days = [
        {
            "date": base_time.strftime("%Y-%m-%d"),
            "date_time": date_string,
            "timed_events": [
                {
                    "description": "#announce",
                    "end_time": None,
                    "owner": "Beth",
                    "recurring": False,
                    "start_time": date_string,
                    "summary": "Take out the bins",
                },
            ],
            "whole_day_events": [],
        }
    ]
    calendar_data = CalendarSource(cache_file_path="").load_data_from_any(days)

    # Avoid hitting gTTS/ffmpeg to build real audio - the content of the
    # generated files isn't what this test is checking.
    monkeypatch.setattr("homeaudio.vcal.notifications.core.text_to_voice_file", lambda text: "fake_speech.mp3")
    monkeypatch.setattr("homeaudio.vcal.notifications.core.join_mp3s_to_wav", lambda files, output: None)
    monkeypatch.setattr("homeaudio.vcal.notifications.core.track_length", lambda path: 0)

    # Stub Snapcast so no real network calls are made to the Snapserver.
    monkeypatch.setattr("homeaudio.vcal.notifications.core.SnapserverManager", StubSnapserverManager)

    # Stub MPD - mpd_connection is a contextmanager, so replace it with a fake
    # one that yields a stub player we can make assertions on.
    mpd_player = StubMpdPlayer()

    @contextmanager
    def fake_mpd_connection(settings=None):
        yield mpd_player

    monkeypatch.setattr("homeaudio.vcal.notifications.core.mpd_connection", fake_mpd_connection)

    check_for_notifications(
        base_time,
        5,
        calendar_data,
        NullScene(),
        event_notification_settings=EventNotificationSettings(notification_rules=[]),
    )

    assert len(mpd_player.play_file_calls) == 1
