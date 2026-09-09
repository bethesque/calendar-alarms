import logging
import os
import time as time_module
from datetime import datetime, time, timedelta
from typing import Callable
from homeaudio.audio.settings import SchoolAnnouncementsSchedule, SchoolAnnouncementsSettings, MpdSettings, SnapcastSettings
from homeaudio.audio.tts_playback import play_tts_audio_file
from homeaudio.audio.sound import join_mp3s_to_wav
from homeaudio.vcal.cal.google_calendar import Event, WeatherForecast, MissingCalendarDataException, CalendarSource, get_events_for_date, CalendarDay
from homeaudio.vcal.notifications.text_to_voice import text_to_voice_file, gtts_tld
from homeaudio.vcal.notifications import OUTPUT_AUDIO_DIRECTORY, PRE_ANNOUNCEMENT_BELL, POST_ANNOUNCEMENT_SILENCE
from homeaudio.env import CALENDAR_DATA_DIRECTORY


logger = logging.getLogger(__name__)

def is_school_holiday(events: list[Event], holiday_keywords: list[str]) -> bool:
    keywords = [keyword.lower() for keyword in holiday_keywords]
    return any(
        keyword in (event.summary or "").lower()
        for event in events
        for keyword in keywords
    )

def is_school_event(event: Event, school_event_keywords: list[str]) -> bool:
    keywords = [keyword.lower() for keyword in school_event_keywords]
    return any(
        keyword in (event.summary or "").lower() or keyword in (event.description or "").lower()
        for keyword in keywords
    )

def get_school_events(events: list[Event], school_event_keywords: list[str]) -> list[Event]:
    return [event for event in events if is_school_event(event, school_event_keywords)]

def get_weather_forecast(events: list[Event]) -> WeatherForecast | None:
    return next((event for event in events if isinstance(event, WeatherForecast)), None)

"""
Build a list of sentences to speak aloud for the school announcement.
"""
def build_text(school_events: list[Event], weather_forecast: WeatherForecast | None = None) -> list[str]:
    sentences = ["It's time to leave for school."]

    if weather_forecast and any(keyword in weather_forecast.summary.lower() for keyword in ("rain", "showers")):
        sentences.append("You may wish to pack an umbrella as there is rain forecast.")

    if school_events:
        sentences.append("Today's school events are:")
        sentences.extend(event.summary + "." for event in school_events if event.summary)
        sentences.append("Have a nice day.")

    logger.info(f"Generated school announcement: {" ".join(sentences)}")
    return sentences

def _datestamp() -> str:
    now = datetime.now()
    return f"{now.strftime('%y%m%d%H%M%S')}{now.microsecond // 1000:03d}"

def build_audio_file(sentences: list[str]) -> str:
    tld = gtts_tld()
    speech_files = [text_to_voice_file(sentence, tld) for sentence in sentences]
    output_file = f"{OUTPUT_AUDIO_DIRECTORY}/school_announcement_{_datestamp()}.wav"
    join_mp3s_to_wav([PRE_ANNOUNCEMENT_BELL] + speech_files + [POST_ANNOUNCEMENT_SILENCE], output_file)
    return output_file

def _seconds_until(target_time: time, now: datetime) -> float:
    target_datetime = datetime.combine(now.date(), target_time, tzinfo=now.tzinfo)
    return max(0.0, (target_datetime - now).total_seconds())

"""
Top level entry point. Announce today's school events, or skip entirely if school is cancelled.
"""
def play_school_announcements(
        calendar_file=os.path.join(CALENDAR_DATA_DIRECTORY, "calendar.json"),
        base_time=datetime.now().astimezone(),
        play_time: time | None = None,
        settings: SchoolAnnouncementsSettings = SchoolAnnouncementsSettings(),
        before_announcement_hook: Callable | None = None,
        after_announcement_hook: Callable | None = None
    ):
    try:
        events = get_events_for_date(CalendarSource(cache_file_path=calendar_file).load_data_from_file(), base_time)
    except MissingCalendarDataException:
        logger.info("No calendar data found for today's date, proceeding with no events.")
        events = []

    if is_school_holiday(events, settings.holiday_keywords):
        logger.info("A holiday keyword matched an event today; skipping school announcement.")
        return

    school_events = get_school_events(events, settings.school_event_keywords)
    weather_forecast = get_weather_forecast(events)
    sentences = build_text(school_events, weather_forecast)
    output_file = build_audio_file(sentences)

    if play_time is not None:
        wait_seconds = _seconds_until(play_time, datetime.now().astimezone())
        logger.info(f"Sleeping {wait_seconds:.1f}s until the scheduled announcement time.")
        time_module.sleep(wait_seconds)

    play_tts_audio_file(output_file, SnapcastSettings(), MpdSettings(), before_announcement_hook, after_announcement_hook)

def _announcement_due(base_time: datetime, window: int, schedule: SchoolAnnouncementsSchedule) -> bool:
    if base_time.weekday() >= 5 or schedule.weekdays is None:
        return False

    scheduled_time = datetime.combine(base_time.date(), schedule.weekdays, tzinfo=base_time.tzinfo)
    return base_time <= scheduled_time < base_time + timedelta(minutes=window)

def check_for_announcement(
        base_time: datetime,
        window: int,
        calendar_days: list[CalendarDay],
        settings: SchoolAnnouncementsSettings = SchoolAnnouncementsSettings()
    ) -> str | None:

    if not settings.enabled:
        return None

    if not _announcement_due(base_time, window, settings.schedule):
        logger.debug(f"School announcements not due {base_time} is not {settings.schedule.weekdays}")
        return None

    try:
        events = get_events_for_date(calendar_days, base_time)
    except MissingCalendarDataException:
        logger.info("No calendar data found for today's date, proceeding with no events.")
        return build_audio_file(["It's time to leave for school.","There was no calendar data found for today's date.", "You may need to fix the authentication."])

    if is_school_holiday(events, settings.holiday_keywords):
        logger.info("A holiday keyword matched an event today; skipping school announcement.")
        return None

    school_events = get_school_events(events, settings.school_event_keywords)
    weather_forecast = get_weather_forecast(events)
    sentences = build_text(school_events, weather_forecast)
    return build_audio_file(sentences)



