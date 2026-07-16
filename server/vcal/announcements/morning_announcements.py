import logging
import glob
import time
from vcal.alarms.mpd import fade_up, mpd_connection
from vcal.announcements.snapcast import SnapserverManager
from vcal.settings import MorningAnnouncementsSettings, MpdSettings, SnapcastSettings
from vcal.cal.google_calendar import Event, WeatherForecast, MissingCalendarDataException, load_data_from_file, get_events_for_date
from vcal.alarms.text_to_voice import text_to_voice_file_daily_summary
from vcal.alarms.sound import mix_announcement_audio, track_length
from vcal.random_text import ListOptionsSource, select_text
from vcal.select_item import select_item_by_date, select_option

from vcal.alarms import BACKGROUND_MUSIC_DIRECTORY, OUTPUT_AUDIO_DIRECTORY
from vcal.env import CACHE_DIRECTORY

MORNING_ANNOUNCEMENTS_AUDIO_FILE = f"{OUTPUT_AUDIO_DIRECTORY}/morning_announcements.wav"
MORNING_ANNOUNCEMENTS_PRELUDE_CHOICES = "morning_announcements_prelude_choices.txt"
SPEECH_FILE = CACHE_DIRECTORY + "/audio/morning_annoucements_speech.mp3"

logger = logging.getLogger(__name__)

class TextBuilder:
    def __init__(self, events: list[Event], settings: MorningAnnouncementsSettings = MorningAnnouncementsSettings()) -> None:
        self.events = events
        self.settings = settings

    def get_morning_announcements_text(self) -> list[str]:
        try:
            sentences = self._build_sentences()

            logger.info(f"Generated daily summary announcement: {" ".join(sentences)}")
            return sentences
        except MissingCalendarDataException:
            return ["There was no calendar data found for today's date. "]

    """
    Build a List of sentences to speak aloud from the given list of Events.
    """
    def _build_sentences(self):
        weather_forecast = self._get_weather_forecast(self.events)
        events = self._get_non_weather_forecast_events(self.events)

        sentences = ["Good morning!"]

        prelude = self._get_prelude()
        if prelude:
            sentences.append(prelude)

        if weather_forecast:
            sentences.append(f"The weather forecast for today is: {weather_forecast.summary}.")

        if events:
            # Collect the summary from each event on the first day and join them together with a ". " separator
            event_summaries = [event.summary + "." for event in events if event.summary]
            sentences.append("Todays events are:")
            sentences.extend(event_summaries)
        else:
            sentences.append("There are no events scheduled for today.")

        sentences.extend(self._get_postlude())

        sentences.append("Have a lovely day.")

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
            return [f"Your fun fact for today is:", fact_text]
        else:
            logger.info("All facts have been used.")
            return []

    def _get_non_weather_forecast_events(self, events):
        return [event for event in events if not isinstance(event, WeatherForecast)]

    def _get_weather_forecast(self, events):
        return next((event for event in events if isinstance(event, WeatherForecast)), None)

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


class AudioFileBuilder:
    def __init__(self, text_builder, bg_music_selector):
        self.text_builder = text_builder
        self.bg_music_selector = bg_music_selector

    def build_audio_file(self):
        speech_file = text_to_voice_file_daily_summary(self.text_builder.get_morning_announcements_text())
        mix_announcement_audio(
            speech_file=speech_file,
            music_file=self.bg_music_selector.get_background_music_file(),
            output_file=MORNING_ANNOUNCEMENTS_AUDIO_FILE
        )
        return MORNING_ANNOUNCEMENTS_AUDIO_FILE

"""
Top level entry point. Generate a summary of today's events, convert them to voice, and play them.
"""
def play_morning_announcements(calendar_file, base_time, before_announcement_hook=None, after_announcement_hook=None):
    events = get_events_for_date(load_data_from_file(calendar_file), base_time)
    text_builder = TextBuilder(events)
    bg_music_selector = BackgroundMusicSelector(base_time)
    output_file = AudioFileBuilder(text_builder, bg_music_selector).build_audio_file()
    play_morning_announcements_audio_file(output_file, SnapcastSettings(), MpdSettings(), before_announcement_hook, after_announcement_hook)

"""
Helper method to play the cached announcement speech audio file to avoid a round trip to the text-to-speech service.
"""
def play_morning_announcements_audio_file(audio_file, snapcast_settings: SnapcastSettings, mpd_settings: MpdSettings, before_announcement_hook=None, after_announcement_hook=None):
    SnapserverManager(snapcast_settings).set_volumes("tts", None)

    before_announcement_hook() if before_announcement_hook else None

    # Play the mixed audio file
    with mpd_connection(mpd_settings) as alarm_player:
        volumes = mpd_settings.volumes
        alarm_player.set_volume(volumes.alarm_start)
        alarm_player.play_file(audio_file)
        fade_up([(alarm_player, volumes.tts)], 5, 10)

    if after_announcement_hook:
        time.sleep(track_length(audio_file))
        after_announcement_hook()