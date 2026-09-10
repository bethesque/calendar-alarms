import sys
from datetime import datetime, time as time_of_day
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import homeaudio.vcal.school_announcements.core as school_announcements_core
from homeaudio.vcal.school_announcements.core import (
    build_text,
    build_audio_file,
    is_school_holiday,
    get_school_events,
    get_weather_forecast,
    _announcement_due,
    _create_audio_file_for_calendar_days,
    _collect_speech_files,
    check_for_announcement,
    play_school_announcements,
    ERROR_MESSAGE_AUDIO,
)
from homeaudio.vcal.cal.google_calendar import Event, WeatherForecast, MissingCalendarDataException
from homeaudio.vcal.event_notifications.text_to_voice import TextToSpeechError
from homeaudio.audio.settings import SchoolAnnouncementsSchedule, SchoolAnnouncementsSettings
from homeaudio.vcal.event_notifications import OUTPUT_AUDIO_DIRECTORY, PRE_ANNOUNCEMENT_BELL, POST_ANNOUNCEMENT_SILENCE

DEFAULT_HOLIDAY_KEYWORDS = ["no school", "school holidays"]
DEFAULT_SCHOOL_EVENT_KEYWORDS = ["school"]

def rand_true():
    return 0

def rand_false():
    return 1


def test_build_text_with_no_school_events():
    assert build_text([], rand=rand_false) == ["It's time to leave for school.", "Have a nice day."]


def test_build_text_lists_school_events():
    school_events = [
        Event(owner="cal", summary="SCHOOL Assembly", description="", calendar_id="id"),
    ]

    assert build_text(school_events, rand=rand_false) == [
        "It's time to leave for school.",
        "Today's school events are:",
        "SCHOOL Assembly.",
        "Have a nice day.",
    ]

def test_build_text_lists_school_events_with_if_you_want():
    school_events = [
        Event(owner="cal", summary="SCHOOL Assembly", description="", calendar_id="id"),
    ]

    assert build_text(school_events, rand=rand_true) == [
        "It's time to leave for school.",
        "Today's school events are:",
        "SCHOOL Assembly.",
        "Have a nice day.",
        "If you want.",
        "I'm not the boss of you.",
    ]


def test_build_text_preserves_event_order_for_multiple_events():
    school_events = [
        Event(owner="cal", summary="School drop off", description="", calendar_id="id"),
        Event(owner="cal", summary="School excursion", description="", calendar_id="id"),
    ]

    assert build_text(school_events, rand=rand_false) == [
        "It's time to leave for school.",
        "Today's school events are:",
        "School drop off.",
        "School excursion.",
        "Have a nice day.",
    ]


def test_build_text_adds_umbrella_reminder_when_forecast_mentions_rain():
    weather_forecast = WeatherForecast(owner="cal", summary="Rain clearing later", description="", calendar_id="id")

    assert build_text([], weather_forecast, rand=rand_false) == [
        "It's time to leave for school.",
        "You may wish to pack an umbrella as there is rain forecast.",
        "Have a nice day.",
    ]


def test_build_text_matches_rain_case_insensitively():
    weather_forecast = WeatherForecast(owner="cal", summary="Possible RAIN", description="", calendar_id="id")

    assert "You may wish to pack an umbrella as there is rain forecast." in build_text([], weather_forecast, rand=rand_false)


def test_build_text_adds_umbrella_reminder_when_forecast_mentions_showers():
    weather_forecast = WeatherForecast(owner="cal", summary="Scattered showers", description="", calendar_id="id")

    assert "You may wish to pack an umbrella as there is rain forecast." in build_text([], weather_forecast, rand=rand_false)


def test_build_text_omits_umbrella_reminder_when_forecast_has_no_rain():
    weather_forecast = WeatherForecast(owner="cal", summary="Sunny", description="", calendar_id="id")

    assert build_text([], weather_forecast, rand=rand_false) == ["It's time to leave for school.", "Have a nice day."]


def test_build_text_omits_umbrella_reminder_when_no_forecast():
    assert build_text([], None, rand=rand_false) == ["It's time to leave for school.", "Have a nice day."]


def test_build_text_puts_umbrella_reminder_before_school_events():
    school_events = [Event(owner="cal", summary="School excursion", description="", calendar_id="id")]
    weather_forecast = WeatherForecast(owner="cal", summary="Heavy rain", description="", calendar_id="id")

    assert build_text(school_events, weather_forecast, rand=rand_false) == [
        "It's time to leave for school.",
        "You may wish to pack an umbrella as there is rain forecast.",
        "Today's school events are:",
        "School excursion.",
        "Have a nice day.",
    ]


def test_get_weather_forecast_returns_the_weather_forecast_event():
    weather_forecast = WeatherForecast(owner="cal", summary="Min 10 Max 20", description="", calendar_id="id")
    events = [Event(owner="cal", summary="Dentist", description="", calendar_id="id"), weather_forecast]

    assert get_weather_forecast(events) is weather_forecast


def test_get_weather_forecast_returns_none_when_absent():
    events = [Event(owner="cal", summary="Dentist", description="", calendar_id="id")]

    assert get_weather_forecast(events) is None


def test_get_school_events_matches_summary_case_insensitively():
    events = [
        Event(owner="cal", summary="SCHOOL Assembly", description="", calendar_id="id"),
        Event(owner="cal", summary="Dentist", description="", calendar_id="id"),
    ]

    assert get_school_events(events, DEFAULT_SCHOOL_EVENT_KEYWORDS) == [events[0]]


def test_get_school_events_matches_description():
    events = [
        Event(owner="cal", summary="Pickup", description="Reminder: School photo day", calendar_id="id"),
        Event(owner="cal", summary="Dentist", description="", calendar_id="id"),
    ]

    assert get_school_events(events, DEFAULT_SCHOOL_EVENT_KEYWORDS) == [events[0]]


def test_get_school_events_with_no_matches():
    events = [
        Event(owner="cal", summary="Dentist", description="", calendar_id="id"),
        Event(owner="cal", summary="Meeting", description="", calendar_id="id"),
    ]

    assert get_school_events(events, DEFAULT_SCHOOL_EVENT_KEYWORDS) == []


def test_build_audio_file_joins_bell_and_speech_files(monkeypatch):
    speech_files_by_sentence = {
        "Sentence one.": "speech1.mp3",
        "Sentence two.": "speech2.mp3",
    }
    monkeypatch.setattr(
        "homeaudio.vcal.school_announcements.core.text_to_voice_file",
        lambda sentence, tld: speech_files_by_sentence[sentence],
    )

    joined = {}

    def fake_join(mp3_files, output_file):
        joined["mp3_files"] = mp3_files
        joined["output_file"] = output_file

    monkeypatch.setattr("homeaudio.vcal.school_announcements.core.join_mp3s_to_wav", fake_join)

    output_file = build_audio_file(["Sentence one.", "Sentence two."])

    assert joined["mp3_files"] == [PRE_ANNOUNCEMENT_BELL, "speech1.mp3", "speech2.mp3", POST_ANNOUNCEMENT_SILENCE]
    assert output_file == joined["output_file"]
    assert output_file.startswith(f"{OUTPUT_AUDIO_DIRECTORY}/school_announcement_")
    assert output_file.endswith(".wav")


def test_collect_speech_files_uses_error_message_audio_in_place_of_first_failed_sentence(monkeypatch):
    monkeypatch.setattr("homeaudio.vcal.school_announcements.core.gtts_tld", lambda: "com")

    def fake_text_to_voice_file(sentence, tld):
        if sentence in ("Sentence one.", "Sentence three."):
            raise TextToSpeechError(sentence)
        return "speech2.mp3"

    monkeypatch.setattr(
        "homeaudio.vcal.school_announcements.core.text_to_voice_file",
        fake_text_to_voice_file,
    )

    speech_files = _collect_speech_files(["Sentence one.", "Sentence two.", "Sentence three."])

    assert speech_files == [ERROR_MESSAGE_AUDIO, "speech2.mp3"]


def test_is_school_holiday_true_when_holiday_keyword_matches_case_insensitively():
    events = [
        Event(owner="cal", summary="no SCHOOL today", description="", calendar_id="id"),
    ]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is True


def test_is_school_holiday_true_for_configured_keyword():
    events = [
        Event(owner="cal", summary="Public Holiday", description="", calendar_id="id"),
    ]

    assert is_school_holiday(events, ["public holiday"]) is True


def test_is_school_holiday_false_when_no_keyword_matches():
    events = [
        Event(owner="cal", summary="School Assembly", description="", calendar_id="id"),
    ]

    assert is_school_holiday(events, DEFAULT_HOLIDAY_KEYWORDS) is False


# Monday/Saturday reference dates, matching the convention used in test_daemon.py.
MONDAY_8_30 = datetime(2026, 4, 27, 8, 30, 0)
SATURDAY_8_30 = datetime(2026, 4, 25, 8, 30, 0)


def test_announcement_due_true_exactly_at_the_scheduled_time():
    schedule = SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0))

    assert _announcement_due(MONDAY_8_30, 1, schedule) is True


def test_announcement_due_true_when_scheduled_time_falls_within_the_window():
    schedule = SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0))
    base_time = datetime(2026, 4, 27, 8, 29, 30)  # Monday, 30s before the scheduled time

    assert _announcement_due(base_time, 1, schedule) is True


def test_announcement_due_false_before_the_window():
    schedule = SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0))
    base_time = datetime(2026, 4, 27, 8, 28, 0)  # Monday, too early

    assert _announcement_due(base_time, 1, schedule) is False


def test_announcement_due_false_after_the_scheduled_time_has_passed():
    schedule = SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0))
    base_time = datetime(2026, 4, 27, 8, 31, 0)  # Monday, already past

    assert _announcement_due(base_time, 1, schedule) is False


def test_announcement_due_false_on_weekends():
    schedule = SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0))

    assert _announcement_due(SATURDAY_8_30, 1, schedule) is False


def test_announcement_due_false_when_weekdays_schedule_unset():
    schedule = SchoolAnnouncementsSchedule(weekdays=None)

    assert _announcement_due(MONDAY_8_30, 1, schedule) is False


def test_check_for_announcement_returns_none_when_settings_disabled():
    settings = SchoolAnnouncementsSettings(enabled=False, schedule=SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0)))

    assert check_for_announcement(MONDAY_8_30, 1, [], settings) is None


def test_check_for_announcement_returns_none_when_not_due():
    settings = SchoolAnnouncementsSettings(enabled=True, schedule=SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0)))
    base_time = datetime(2026, 4, 27, 8, 0, 0)  # Monday, well before 8:30

    assert check_for_announcement(base_time, 1, [], settings) is None


def test_check_for_announcement_builds_the_audio_file_when_due(monkeypatch):
    settings = SchoolAnnouncementsSettings(enabled=True, schedule=SchoolAnnouncementsSchedule(weekdays=time_of_day(8, 30, 0)))

    seen = {}

    def fake_create_audio_file(base_time, calendar_days, s):
        seen["args"] = (base_time, calendar_days, s)
        return "school_announcement.wav"

    monkeypatch.setattr(school_announcements_core, "_create_audio_file_for_calendar_days", fake_create_audio_file)

    result = check_for_announcement(MONDAY_8_30, 1, "calendar-days", settings)

    assert result == "school_announcement.wav"
    assert seen["args"] == (MONDAY_8_30, "calendar-days", settings)


def test_create_audio_file_for_calendar_days_returns_none_when_school_holiday(monkeypatch):
    events = [Event(owner="cal", summary="NO SCHOOL today", description="", calendar_id="id")]
    monkeypatch.setattr(school_announcements_core, "get_events_for_date", lambda calendar_days, base_time: events)

    settings = SchoolAnnouncementsSettings(holiday_keywords=DEFAULT_HOLIDAY_KEYWORDS, school_event_keywords=DEFAULT_SCHOOL_EVENT_KEYWORDS)

    assert _create_audio_file_for_calendar_days(MONDAY_8_30, [], settings) is None


def test_create_audio_file_for_calendar_days_builds_audio_when_not_a_holiday(monkeypatch):
    events = [Event(owner="cal", summary="School excursion", description="", calendar_id="id")]
    monkeypatch.setattr(school_announcements_core, "get_events_for_date", lambda calendar_days, base_time: events)
    monkeypatch.setattr(
        school_announcements_core,
        "build_text",
        lambda school_events, weather_forecast=None: build_text(school_events, weather_forecast, rand=rand_false),
    )

    seen_sentences = {}

    def fake_build_audio_file(sentences):
        seen_sentences["sentences"] = sentences
        return "built.wav"

    monkeypatch.setattr(school_announcements_core, "build_audio_file", fake_build_audio_file)

    settings = SchoolAnnouncementsSettings(holiday_keywords=DEFAULT_HOLIDAY_KEYWORDS, school_event_keywords=DEFAULT_SCHOOL_EVENT_KEYWORDS)

    assert _create_audio_file_for_calendar_days(MONDAY_8_30, [], settings) == "built.wav"
    assert seen_sentences["sentences"] == build_text(events, rand=rand_false)


def test_create_audio_file_for_calendar_days_falls_back_when_calendar_data_missing(monkeypatch):
    def raise_missing(calendar_days, base_time):
        raise MissingCalendarDataException("no calendar data")

    monkeypatch.setattr(school_announcements_core, "get_events_for_date", raise_missing)
    monkeypatch.setattr(school_announcements_core, "build_audio_file", lambda sentences: "fallback.wav")

    settings = SchoolAnnouncementsSettings(holiday_keywords=DEFAULT_HOLIDAY_KEYWORDS, school_event_keywords=DEFAULT_SCHOOL_EVENT_KEYWORDS)

    assert _create_audio_file_for_calendar_days(MONDAY_8_30, [], settings) == "fallback.wav"


def test_play_school_announcements_builds_and_plays_the_audio_file(monkeypatch):
    settings = SchoolAnnouncementsSettings(holiday_keywords=[], school_event_keywords=DEFAULT_SCHOOL_EVENT_KEYWORDS)

    class FakeCalendarSource:
        def __init__(self, cache_file_path):
            pass

        def load_data_from_file(self):
            return "calendar-days"

    monkeypatch.setattr(school_announcements_core, "CalendarSource", FakeCalendarSource)

    seen = {}

    def fake_create_audio_file(base_time, calendar_days, s):
        seen["args"] = (base_time, calendar_days, s)
        return "built.wav"

    monkeypatch.setattr(school_announcements_core, "_create_audio_file_for_calendar_days", fake_create_audio_file)

    play_calls = []
    monkeypatch.setattr(
        school_announcements_core,
        "play_tts_audio_file",
        lambda file, snapcast_settings, mpd_settings, before_hook, after_hook: play_calls.append((file, before_hook, after_hook)),
    )

    before_hook = lambda: None
    after_hook = lambda: None

    play_school_announcements(base_time=MONDAY_8_30, settings=settings, before_announcement_hook=before_hook, after_announcement_hook=after_hook)

    assert seen["args"] == (MONDAY_8_30, "calendar-days", settings)
    assert play_calls == [("built.wav", before_hook, after_hook)]
