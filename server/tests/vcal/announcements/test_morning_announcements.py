import sys
import os
from datetime import datetime, time as time_of_day
from pathlib import Path
from unittest.mock import Mock

from homeaudio.vcal.playback import NotificationFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import homeaudio.vcal.morning_announcements as morning_announcements_core
from homeaudio.vcal.morning_announcements import (
    TextBuilder,
    _announcement_due,
    _collect_speech_files,
    _create_audio_file_for_calendar_days,
    check_for_announcement,
    play_morning_announcements,
    ERROR_MESSAGE_AUDIO,
)
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarDayList, Event, WeatherForecast, MissingCalendarDataException
from homeaudio.vcal.event_notifications.text_to_voice import TextToSpeechError
from homeaudio.vcal import MORNING_GREETING, NO_EVENTS_TODAY, HAVE_A_LOVELY_DAY
from homeaudio.audio.settings import MorningAnnouncementsSchedule, MorningAnnouncementsSettings

select_option_call_count = 0

def test_error_message_audio_file_exists():
    assert os.path.exists(ERROR_MESSAGE_AUDIO) is True

def fake_select_option(opts):
    global select_option_call_count
    select_option_call_count += 1
    if select_option_call_count == 1:
        return Mock(text="Prelude text.")
    return Mock(text="Selected fact")

def test_get_morning_announcements_text_includes_weather_and_facts(monkeypatch):
    # Create three events: two normal and one weather forecast
    e1 = Event(owner="cal", summary="Meeting", description="", calendar_id="id")
    e2 = Event(owner="cal", summary="Appointment", description="", calendar_id="id")
    weather = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="", calendar_id="id")

    events = [e1, e2]

    monkeypatch.setattr(
        "homeaudio.vcal.morning_announcements.select_option",
        fake_select_option,
    )

    # Provide a minimal settings object with needed attributes
    settings = Mock()
    settings.enabled_prelude_options = ["Prelude text."]
    settings.prelude_probability = 1.0
    settings.unused_facts = ["fact1"]
    settings.save = Mock()

    tb = TextBuilder(events, [weather], settings)

    text = tb.get_morning_announcements_text()

    expected = [ "Good morning!",
        "Prelude text.",
        "The weather forecast for today is: Min 10 Max 20.",
        "Todays events are:",
        "Meeting",
        "Appointment",
        "Your fun fact for today is:",
        "Selected fact",
        "Have a lovely day.",
    ]
    assert text == expected


def _event_summaries(events):
    settings = Mock(enabled_prelude_options=[], unused_facts=[])
    sentences = TextBuilder(events, [], settings).get_morning_announcements_text()
    return sentences[sentences.index("Todays events are:") + 1:-1]


def test_get_morning_announcements_text_prefixes_single_owner_events_with_owner():
    events = [Event(owner="Kay", summary="Swimming", description="", calendar_id="id", owner_count=1)]

    assert _event_summaries(events) == ["Kay Swimming"]


def test_get_morning_announcements_text_does_not_prefix_owner_already_in_summary():
    events = [Event(owner="Kay", summary="Kay to dentist", description="", calendar_id="id", owner_count=1)]

    assert _event_summaries(events) == ["Kay to dentist"]


def test_get_morning_announcements_text_does_not_prefix_unowned_or_group_events():
    events = [
        Event(owner="Family", summary="Bin night", description="", calendar_id="id", owner_count=0),
        Event(owner="Kids", summary="School", description="", calendar_id="id", owner_count=2),
    ]

    assert _event_summaries(events) == ["Bin night", "School"]


def test_get_morning_announcements_text_removes_duplicates_keeping_first_occurrence():
    events = [
        Event(owner="Family", summary="Bin night", description="", calendar_id="id"),
        Event(owner="Kay", summary="Swimming", description="", calendar_id="id", owner_count=1),
        Event(owner="Family", summary="Bin night", description="", calendar_id="id2"),
        Event(owner="Pat", summary="Swimming", description="", calendar_id="id", owner_count=1),
        Event(owner="Kay", summary="Swimming", description="", calendar_id="id", owner_count=1),
    ]

    assert _event_summaries(events) == ["Bin night", "Kay Swimming", "Pat Swimming"]


def test_get_morning_announcements_text_skips_events_without_a_summary():
    events = [
        Event(owner="Kay", summary=None, description="", calendar_id="id", owner_count=1),
        Event(owner="Family", summary="", description="", calendar_id="id"),
        Event(owner="Family", summary="Bin night", description="", calendar_id="id"),
    ]

    assert _event_summaries(events) == ["Bin night"]


def test_get_morning_announcements_text_says_no_events_when_there_are_no_events():
    settings = Mock(enabled_prelude_options=[], unused_facts=[])

    assert TextBuilder([], [], settings).get_morning_announcements_text() == [MORNING_GREETING, NO_EVENTS_TODAY, HAVE_A_LOVELY_DAY]


def test_get_morning_announcements_text_says_no_events_when_no_event_has_a_summary():
    events = [Event(owner="Kay", summary=None, description="", calendar_id="id", owner_count=1)]
    settings = Mock(enabled_prelude_options=[], unused_facts=[])

    assert TextBuilder(events, [], settings).get_morning_announcements_text() == [MORNING_GREETING, NO_EVENTS_TODAY, HAVE_A_LOVELY_DAY]


# Monday/Saturday reference dates, matching the convention used in test_daemon.py.
MONDAY_7_17 = datetime(2026, 4, 27, 7, 17, 0)
SATURDAY_9_57 = datetime(2026, 4, 25, 9, 57, 0)

DEFAULT_SCHEDULE = MorningAnnouncementsSchedule(weekdays=time_of_day(7, 17, 0), weekends=time_of_day(9, 57, 0))


def test_announcement_due_true_exactly_at_the_weekday_scheduled_time():
    assert _announcement_due(MONDAY_7_17, 1, DEFAULT_SCHEDULE, []) is True


def test_announcement_due_true_exactly_at_the_weekend_scheduled_time():
    assert _announcement_due(SATURDAY_9_57, 1, DEFAULT_SCHEDULE, []) is True


def test_announcement_due_false_before_the_window():
    base_time = datetime(2026, 4, 27, 7, 15, 0)  # Monday, too early

    assert _announcement_due(base_time, 1, DEFAULT_SCHEDULE, []) is False


def test_announcement_due_false_after_the_scheduled_time_has_passed():
    base_time = datetime(2026, 4, 27, 7, 18, 0)  # Monday, already past

    assert _announcement_due(base_time, 1, DEFAULT_SCHEDULE, []) is False


def test_announcement_due_false_when_weekdays_schedule_unset_on_a_weekday():
    schedule = MorningAnnouncementsSchedule(weekdays=None, weekends=time_of_day(9, 57, 0))

    assert _announcement_due(MONDAY_7_17, 1, schedule, []) is False


def test_announcement_due_uses_the_holidays_time_on_a_weekday_holiday():
    schedule = DEFAULT_SCHEDULE.model_copy(update={"holidays": time_of_day(8, 45, 0)})
    calendar_days = CalendarDayList([CalendarDay(date=MONDAY_7_17.date(), holiday=True)])

    assert _announcement_due(MONDAY_7_17, 1, schedule, calendar_days) is False
    assert _announcement_due(MONDAY_7_17.replace(hour=8, minute=45), 1, schedule, calendar_days) is True


def test_announcement_due_uses_the_weekends_time_on_a_weekend_holiday():
    schedule = DEFAULT_SCHEDULE.model_copy(update={"holidays": time_of_day(8, 45, 0)})
    calendar_days = CalendarDayList([CalendarDay(date=SATURDAY_9_57.date(), holiday=True)])

    assert _announcement_due(SATURDAY_9_57, 1, schedule, calendar_days) is True


def test_announcement_due_false_when_holidays_schedule_unset_on_a_holiday():
    schedule = DEFAULT_SCHEDULE.model_copy(update={"holidays": None})
    calendar_days = CalendarDayList([CalendarDay(date=MONDAY_7_17.date(), holiday=True)])

    assert _announcement_due(MONDAY_7_17, 1, schedule, calendar_days) is False


def test_check_for_announcement_returns_none_at_the_weekday_time_on_a_holiday():
    schedule = DEFAULT_SCHEDULE.model_copy(update={"holidays": time_of_day(8, 45, 0)})
    settings = MorningAnnouncementsSettings(enabled=True, schedule=schedule)
    calendar_days = CalendarDayList([CalendarDay(date=MONDAY_7_17.date(), holiday=True)])

    assert check_for_announcement(MONDAY_7_17, 1, calendar_days, "com", settings) is None


def test_announcement_due_false_when_weekends_schedule_unset_on_a_weekend():
    schedule = MorningAnnouncementsSchedule(weekdays=time_of_day(7, 17, 0), weekends=None)

    assert _announcement_due(SATURDAY_9_57, 1, schedule, []) is False


def test_check_for_announcement_returns_none_when_settings_disabled():
    settings = MorningAnnouncementsSettings(enabled=False, schedule=DEFAULT_SCHEDULE)

    assert check_for_announcement(MONDAY_7_17, 1, [], "com", settings) is None


def test_check_for_announcement_returns_none_when_not_due():
    settings = MorningAnnouncementsSettings(enabled=True, schedule=DEFAULT_SCHEDULE)
    base_time = datetime(2026, 4, 27, 7, 0, 0)  # Monday, well before 7:17

    assert check_for_announcement(base_time, 1, [], "com", settings) is None


def test_check_for_announcement_builds_the_audio_file_when_due(monkeypatch):
    settings = MorningAnnouncementsSettings(enabled=True, schedule=DEFAULT_SCHEDULE)

    seen = {}

    def fake_create_audio_file(base_time, calendar_days, tld, s):
        seen["args"] = (base_time, calendar_days, tld, s)
        return "morning_announcement.wav"

    monkeypatch.setattr(morning_announcements_core, "_create_audio_file_for_calendar_days", fake_create_audio_file)

    calendar_days = CalendarDayList([CalendarDay(date=MONDAY_7_17.date())])

    result = check_for_announcement(MONDAY_7_17, 1, calendar_days, "com", settings)

    assert result == NotificationFile(path="morning_announcement.wav")
    assert seen["args"] == (MONDAY_7_17, calendar_days, "com", settings)


def _fake_settings():
    settings = Mock()
    settings.enabled_prelude_options = []
    settings.unused_facts = []
    settings.save = Mock()
    return settings


class _FakeBackgroundMusicSelector:
    def __init__(self, base_time):
        self.base_time = base_time

    def get_background_music_file(self):
        return "music.mp3"


def test_create_audio_file_for_calendar_days_builds_the_audio_file(monkeypatch):
    calendar_days = CalendarDayList([CalendarDay(
        date=MONDAY_7_17.date(),
        whole_day_events=[Event(owner="cal", summary="Meeting", description="", calendar_id="id")],
        weather_forecasts=[WeatherForecast(owner="cal", summary="Min 10 Max 20", description="", calendar_id="id")],
    )])
    monkeypatch.setattr(morning_announcements_core, "BackgroundMusicSelector", _FakeBackgroundMusicSelector)

    seen = {}

    def fake_build_audio_file(sentences, tld, music_file):
        seen["args"] = (sentences, music_file)
        return "built.wav"

    monkeypatch.setattr(morning_announcements_core, "build_audio_file", fake_build_audio_file)

    assert _create_audio_file_for_calendar_days(MONDAY_7_17, calendar_days, "com", _fake_settings()) == "built.wav"
    sentences, music_file = seen["args"]
    assert music_file == "music.mp3"
    assert "Meeting" in sentences
    assert "The weather forecast for today is: Min 10 Max 20." in sentences


def test_create_audio_file_for_calendar_days_proceeds_with_no_events_when_calendar_data_missing(monkeypatch):
    monkeypatch.setattr(morning_announcements_core, "BackgroundMusicSelector", _FakeBackgroundMusicSelector)

    seen = {}

    def fake_build_audio_file(sentences, tld, music_file):
        seen["args"] = (sentences, music_file)
        return "fallback.wav"

    monkeypatch.setattr(morning_announcements_core, "build_audio_file", fake_build_audio_file)

    assert _create_audio_file_for_calendar_days(MONDAY_7_17, [], "com", _fake_settings()) == "fallback.wav"
    sentences, music_file = seen["args"]
    assert music_file == "music.mp3"
    assert "There are no events scheduled for today." in sentences


class _FakeCalendarSource:
    def __init__(self, cache_file_path):
        pass

    def load_data_from_file(self):
        return "calendar-days"


def test_play_morning_announcements_builds_and_plays_the_audio_file(monkeypatch):
    settings = MorningAnnouncementsSettings()

    monkeypatch.setattr(morning_announcements_core, "CalendarSource", _FakeCalendarSource)

    seen = {}

    def fake_create_audio_file(base_time, calendar_days, tld, s):
        seen["args"] = (base_time, calendar_days, s)
        return "built.wav"

    monkeypatch.setattr(morning_announcements_core, "_create_audio_file_for_calendar_days", fake_create_audio_file)

    play_calls = []
    monkeypatch.setattr(
        morning_announcements_core,
        "play_tts_audio_file",
        lambda audio_file, snapcast_settings, mpd_settings, before_hook, after_hook: play_calls.append((audio_file, before_hook, after_hook)),
    )

    before_hook = lambda: None
    after_hook = lambda: None

    play_morning_announcements(base_time=MONDAY_7_17, settings=settings, before_announcement_hook=before_hook, after_announcement_hook=after_hook)

    assert seen["args"] == (MONDAY_7_17, "calendar-days", settings)
    assert play_calls == [("built.wav", before_hook, after_hook)]


def test_collect_speech_files_uses_error_message_audio_in_place_of_first_failed_sentence(monkeypatch):

    def fake_text_to_voice_file(sentence, tld):
        if sentence in ("Sentence one.", "Sentence three."):
            raise TextToSpeechError(sentence)
        return "speech2.mp3"

    monkeypatch.setattr(morning_announcements_core, "text_to_voice_file", fake_text_to_voice_file)

    speech_files = _collect_speech_files(["Sentence one.", "Sentence two.", "Sentence three."], "com")

    assert speech_files == [ERROR_MESSAGE_AUDIO, "speech2.mp3"]
