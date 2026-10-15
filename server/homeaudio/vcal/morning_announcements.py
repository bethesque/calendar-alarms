import logging
import glob
from datetime import datetime, timedelta
from typing import Callable
from homeaudio.audio.settings import CalendarSetting, GoogleCalendarSettings, MorningAnnouncementsSchedule, MorningAnnouncementsSettings, MpdSettings, SnapcastSettings
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarDayList, CalendarEvent, WeatherForecast, MissingCalendarDataException, CalendarSource, DATA_FILE
from homeaudio.vcal.event_notifications.text_to_voice import gtts_tld, text_to_voice_file, TextToSpeechError
from homeaudio.vcal import NO_CALENDAR_DATA, MORNING_GREETING, TODAYS_EVENTS_ARE, FUN_FACT_FOR_TODAY, NO_EVENTS_TODAY, HAVE_A_LOVELY_DAY
from homeaudio.audio.sound import join_mp3s_to_wav, mix_announcement_audio
from homeaudio.audio.select_item import select_item_by_date, select_option
from homeaudio.env import DEFAULT_GOOGLE_TRANSLATE_TLD
from homeaudio.vcal.event_notifications import BACKGROUND_MUSIC_DIRECTORY, OUTPUT_AUDIO_DIRECTORY, POST_ANNOUNCEMENT_SILENCE
from homeaudio.vcal.playback import NotificationFile, NotificationFiles, play_notifications
from homeaudio.vcal.notification_schedule import morning_announcement_time_for_day
from homeaudio.audio.scene import SceneProtocol, scene_for_env

logger = logging.getLogger(__name__)

# gtts-cli  "An error occurred generating the morning announcements. Some of the notifications may have been missing. Please check the calendar for today's events." > audio_resources/morning_announcements_error_message.mp3
ERROR_MESSAGE_AUDIO = "audio_resources/morning_announcements_error_message.mp3"

class TextBuilder:
    def __init__(self, events: list[CalendarEvent], weather_forecasts: list[WeatherForecast], settings: MorningAnnouncementsSettings | None = None) -> None:
        self.events = events
        self.weather_forecasts = weather_forecasts
        self.settings = settings or MorningAnnouncementsSettings()

    def get_morning_announcements_text(self) -> list[str]:
        try:
            sentences = self._build_sentences()

            logger.info(f"Generated daily summary announcement: {" ".join(sentences)}")
            return sentences
        except MissingCalendarDataException:
            return [NO_CALENDAR_DATA]

    """
    Build a List of sentences to speak aloud from the given list of Events.
    """
    def _build_sentences(self):
        sentences = [MORNING_GREETING]

        prelude = self._get_prelude()
        if prelude:
            sentences.append(prelude)

        if self.weather_forecasts:
            summaries = ". ".join(forecast.summary.rstrip(".") for forecast in self.weather_forecasts)
            sentences.append(f"The weather forecast for today is: {summaries}.")

        # non_owned_events = [e for e in events if e.owner_count == 0]
        # events_by_owner = {owner: [e for e in events if e.owner == owner] for owner in dict.fromkeys(e.owner for e in events if e.owner_count == 1)}
        # group_events = [e for e in events if e.owner_count > 1]

        # sentence_parts = []

        # # non owned events
        # summaries = dict.fromkeys(e.summary for e in non_owned_events)
        # sentence_parts.extend(summaries)

        # # single owner events
        # for owner, owned_events in events_by_owner.items():
        #     sentence_parts.append(owner + ":")
        #     summaries = dict.fromkeys(e.summary for e in owned_events)
        #     sentence_parts.extend(summaries)

        # # group owned events
        # summaries = dict.fromkeys(e.summary for e in group_events)
        # sentence_parts.extend(summaries)

        sentence_parts = []
        for event in self.events:
            if event.summary:
                if event.owner_count == 1 and not event.owner in event.summary:
                    next_part = event.owner + " " + event.summary
                else:
                    next_part = event.summary

                if not next_part in sentence_parts:
                    sentence_parts.append(next_part)

        if sentence_parts:
            sentences.append(TODAYS_EVENTS_ARE)
            sentences.extend(sentence_parts)
        else:
            sentences.append(NO_EVENTS_TODAY)


        sentences.extend(self._get_postlude())

        sentences.append(HAVE_A_LOVELY_DAY)

        return sentences

    def _get_prelude(self)-> str | None:
        options = self.settings.enabled_prelude_options
        if options:
            prelude_text = select_option(self.settings.enabled_prelude_options).text
            self.settings.save()
            return prelude_text
        else:
            return None

    def _get_postlude(self)-> list[str]:
        unused_facts = self.settings.unused_facts
        if unused_facts:
            fact_text = select_option(unused_facts).text
            self.settings.save()  # Save the updated last_used timestamps for the selected facts
            return [FUN_FACT_FOR_TODAY, fact_text]
        else:
            logger.debug("All facts have been used.")
            return []

class BackgroundMusicSelector:
    def __init__(self, base_time):
        self.base_time = base_time

    def get_background_music_file(self) -> str:
        background_music_files = self._get_background_music_files()
        # New background music every 14 days
        return select_item_by_date(sorted(background_music_files), self.base_time.date(), 14)

    def _get_background_music_files(self):
        # Get all mp3 files in the BACKGROUND_MUSIC_DIRECTORY
        background_music_files = glob.glob(f"{BACKGROUND_MUSIC_DIRECTORY}/*.mp3")
        if not background_music_files:
            raise FileNotFoundError(f"No background music files found in {BACKGROUND_MUSIC_DIRECTORY}")
        return background_music_files


def build_audio_file(sentences: list[str], tld: str, music_file: str) -> str:
    datestr = _datestamp()
    speech_files = _collect_speech_files(sentences, tld)
    joined_speech_file = f"{OUTPUT_AUDIO_DIRECTORY}/morning_announcements_speech_{datestr}.wav"
    join_mp3s_to_wav(speech_files + [POST_ANNOUNCEMENT_SILENCE], joined_speech_file)

    output_file = f"{OUTPUT_AUDIO_DIRECTORY}/morning_announcements_{datestr}.wav"

    mix_announcement_audio(
        speech_file=joined_speech_file,
        music_file=music_file,
        output_file=output_file
    )
    return output_file

def _collect_speech_files(sentences: list[str], tld: str) -> list[str]:
    speech_files = []
    error = False
    for sentence in sentences:
        try:
            speech_files.append(text_to_voice_file(sentence, tld))
        except TextToSpeechError:
            if not error:
                speech_files.append(ERROR_MESSAGE_AUDIO)
                error = True
    return speech_files

def _datestamp() -> str:
    now = datetime.now()
    return f"{now.strftime('%y%m%d%H%M%S')}{now.microsecond // 1000:03d}"

def _announcement_due(base_time: datetime, window: int, schedule: MorningAnnouncementsSchedule, calendar_days: CalendarDayList) -> bool:
    scheduled_time_of_day = morning_announcement_time_for_day(schedule, base_time.date(), calendar_days)
    if scheduled_time_of_day is None:
        return False

    scheduled_time = datetime.combine(base_time.date(), scheduled_time_of_day, tzinfo=base_time.tzinfo)
    return base_time <= scheduled_time < base_time + timedelta(minutes=window)

def _excluded_calendar_ids(calendars: list[CalendarSetting]) -> set[str]:
    return {calendar.id for calendar in calendars if not calendar.include_in_morning_announcements}

def _create_audio_file_for_calendar_days(base_time: datetime, calendar_days: CalendarDayList, tld: str, settings: MorningAnnouncementsSettings | None = None, calendars: list[CalendarSetting] | None = None) -> str:
    settings = settings or MorningAnnouncementsSettings()
    calendars = GoogleCalendarSettings().calendars if calendars is None else calendars
    excluded_calendar_ids = _excluded_calendar_ids(calendars)
    try:
        calendar_day = calendar_days.get_calendar_day_for_date(base_time)
        events = [event for event in calendar_day.all_events() if event.calendar_id not in excluded_calendar_ids]
        weather_forecasts = calendar_day.weather_forecasts
    except MissingCalendarDataException:
        logger.info(f"No calendar data found for today's date ({base_time}), proceeding with no events.")
        events = []
        weather_forecasts = []

    text_builder = TextBuilder(events, weather_forecasts, settings)
    bg_music_selector = BackgroundMusicSelector(base_time)
    return build_audio_file(text_builder.get_morning_announcements_text(), tld, bg_music_selector.get_background_music_file())

"""
Called by the notifications daemon on every tick (homeaudio/vcal/notifications/core.py). Returns
the built audio file if the morning announcement is due this tick, or None otherwise.
"""
def check_for_announcement(
        base_time: datetime,
        window: int,
        calendar_days: CalendarDayList,
        tld: str,
        settings: MorningAnnouncementsSettings | None = None,
        google_calendar_settings: GoogleCalendarSettings | None = None
    ) -> NotificationFile | None:
    settings = settings or MorningAnnouncementsSettings()
    google_calendar_settings = google_calendar_settings or GoogleCalendarSettings()

    if not settings.enabled:
        logger.debug(f"Morning announcements disabled")
        return None

    if not _announcement_due(base_time, window, settings.schedule, calendar_days):
        logger.debug(f"Morning announcements not due")
        return None

    return NotificationFile(path=_create_audio_file_for_calendar_days(base_time, calendar_days, tld, settings, google_calendar_settings.calendars))

"""
Entry point for UI. Generate a summary of today's events, convert them to voice, and play them.
"""
def play_morning_announcements(
        base_time: datetime | None = None,
        calendar_file = DATA_FILE,
        settings: MorningAnnouncementsSettings | None = None,
        google_calendar_settings: GoogleCalendarSettings | None = None,
        scene: SceneProtocol | None = None
    ):
    logger.debug(f"Loading calendar data from {calendar_file}")
    base_time = base_time or datetime.now().astimezone()
    settings = settings or MorningAnnouncementsSettings()
    google_calendar_settings = google_calendar_settings or GoogleCalendarSettings()
    scene = scene or scene_for_env()

    calendar_days = CalendarSource(cache_file_path=calendar_file).load_data_from_file()
    output_file = _create_audio_file_for_calendar_days(base_time, calendar_days, DEFAULT_GOOGLE_TRANSLATE_TLD, settings, google_calendar_settings.calendars)

    notification_files = NotificationFiles(scheduled_announcements_files=[NotificationFile(output_file)])
    play_notifications(notification_files, scene)
