import logging
import glob
import random
import time
from datetime import datetime
from vcal.alarms.alarm import set_snapclients_to_max_volume
from vcal.scene import SceneProtocol
from vcal.alarms.mpd import fade_up, mpd_connection
from vcal.cal.google_calendar import WeatherForecast, load_data_from_file
from vcal.alarms.text_to_voice import text_to_voice_file_daily_summary, text_to_voice_file
from vcal.alarms.sound import mix_announcement_audio, track_length, join_mp3s_to_wav
from vcal.random_text import FileListOptionsSource, TextFileOptionsSource, select_text
from vcal.select_item import select_item_by_date
from vcal.env import DATA_DIRECTORY, CACHE_DIRECTORY, OUTPUT_AUDIO_DIRECTORY, INITIAL_ALARM_VOLUME, ANNOUNCEMENT_VOLUME, ANNOUNCEMENT_SOUND_EFFECT_PROBABILITY
from vcal.alarms import BACKGROUND_MUSIC_DIRECTORY, AUDIO_DIRECTORY

CALENDAR_FILE = f"{DATA_DIRECTORY}/calendar.json"
SPEECH_FILE = CACHE_DIRECTORY + "/audio/morning_annoucements_speech.mp3"
MORNING_ANNOUNCEMENTS_AUDIO_FILE = f"{OUTPUT_AUDIO_DIRECTORY}/morning_announcements.wav"
SILENCE_5_SEC = "audio/silence_5s.mp3"
SILENCE_1_SEC = "audio/silence_1s.mp3"
SILENCE_HALF_SEC = "audio/silence_500ms.mp3"
MORNING_ANNOUNCEMENTS_PRELUDE_CHOICES = "morning_announcements_prelude_choices.txt"
PRE_ANNOUNCEMENT_BELL = AUDIO_DIRECTORY + "/preannounce_0_3_vol.mp3"

logger = logging.getLogger(__name__)

class MissingCalendarDataException(Exception):
    pass

def play_announcement(message: str, scene: SceneProtocol):
    announcement_file = _build_one_off_announcement_file(message)
    set_snapclients_to_max_volume()

    def play():
        try:
            with mpd_connection() as alarm_player:
                alarm_player.set_volume(ANNOUNCEMENT_VOLUME)
                alarm_player.play_file(announcement_file)
                time.sleep(track_length(announcement_file))
        except Exception:
            logger.exception(f"Error playing announcement audio file {announcement_file}")

    scene.around_announcement(play)

def _build_one_off_announcement_file(message: str):
    speech_file = text_to_voice_file(message)
    announcement_file = OUTPUT_AUDIO_DIRECTORY + "/one_off_announcement.wav"
    files = get_pre_announcement_files() + [speech_file, SILENCE_1_SEC]
    join_mp3s_to_wav(files, announcement_file)
    return announcement_file

def get_pre_announcement_files()-> list[str]:
    files = [PRE_ANNOUNCEMENT_BELL]
    sound_effect = select_text(None, ANNOUNCEMENT_SOUND_EFFECT_PROBABILITY, FileListOptionsSource(directory=AUDIO_DIRECTORY + "/sound_effects", extensions=[".mp3"]))
    if sound_effect:
        files.append(sound_effect)
        files.append(SILENCE_HALF_SEC)
    return files

"""
Top level entry point. Generate a summary of today's events, convert them to voice, and play them.
"""
def play_morning_announcements(calendar_file, base_time, before_announcement_hook=None, after_announcement_hook=None):
    output_file = build_morning_announcements_audio_file(calendar_file, base_time, get_background_music_file())
    play_morning_announcements_audio_file(output_file, before_announcement_hook, after_announcement_hook)

"""
Helper method to play the cached announcement speech audio file to avoid a round trip to the text-to-speech service.
"""
def play_morning_announcements_audio_file(audio_file, before_announcement_hook=None, after_announcement_hook=None):

    before_announcement_hook() if before_announcement_hook else None

    # Play the mixed audio file
    with mpd_connection() as alarm_player:
        alarm_player.set_volume(INITIAL_ALARM_VOLUME)
        alarm_player.play_file(audio_file)
        fade_up([(alarm_player, ANNOUNCEMENT_VOLUME)], 5, 10)

    if after_announcement_hook:
        time.sleep(track_length(MORNING_ANNOUNCEMENTS_AUDIO_FILE))
        after_announcement_hook()

def build_morning_announcements_audio_file(calendar_file, base_time, background_music_file):
    speech_file = get_morning_announcements_speech_file(calendar_file, base_time)
    mix_announcement_audio(
        speech_file=speech_file,
        music_file=background_music_file,
        output_file=MORNING_ANNOUNCEMENTS_AUDIO_FILE
    )
    return MORNING_ANNOUNCEMENTS_AUDIO_FILE

"""
Generate the voice file from the calendar events in the given file, and return the
path to the voice file.
"""
def get_morning_announcements_speech_file(calendar_file, base_time):
    return text_to_voice_file_daily_summary(get_morning_announcements_text(calendar_file, base_time))

def get_morning_announcements_text(calendar_file, base_time):
    try:
        announcement = " ".join(build_sentences(get_events(calendar_file, base_time)))
        logger.info(f"Generated daily summary announcement: {announcement}")
        return announcement
    except MissingCalendarDataException:
        return "There was no calendar data found for today's date. "


def get_events(calendar_file, base_time):
    # Array of CalendarDay objects
    # TODO only get today's events, not all events in the file
    calendar_days = load_data_from_file(calendar_file)

    match = next((day for day in calendar_days if day.date == base_time.date()), None)
    if match:
        return match.all_events()
    else:
        raise MissingCalendarDataException()

"""
Build a List of sentences to speak aloud from the given list of Events.
"""
def build_sentences(all_events):
    weather_forecast = get_weather_forecast(all_events)
    events = get_non_weather_forecast_events(all_events)

    sentences = ["Good morning!"]

    extra_text = select_text(None, 1, TextFileOptionsSource(file_name=MORNING_ANNOUNCEMENTS_PRELUDE_CHOICES) )
    if extra_text:
        sentences.append(extra_text)

    if weather_forecast:
        sentences.append(f"The weather forecast for today is: {weather_forecast.summary}.")

    if events:
        # Collect the summary from each event on the first day and join them together with a ". " separator
        event_summaries = [event.summary + "." for event in events if event.summary]
        sentences.append("Todays events are:")
        sentences.extend(event_summaries)
    else:
        sentences.append("There are no events scheduled for today.")

    sentences.append("Have a lovely day.")

    return sentences

def get_non_weather_forecast_events(events):
    return [event for event in events if not isinstance(event, WeatherForecast)]

def get_weather_forecast(events):
    return next((event for event in events if isinstance(event, WeatherForecast)), None)

def get_background_music_file(date=None):
    background_music_files = get_background_music_files()
    if date is None:
        date = datetime.now().date()
    # New background music every 14 days
    return select_item_by_date(sorted(background_music_files), date, 14)

def get_background_music_files():
    # Get all mp3 files in the BACKGROUND_MUSIC_DIRECTORY
    background_music_files = glob.glob(f"{BACKGROUND_MUSIC_DIRECTORY}/*.mp3")
    if not background_music_files:
        raise FileNotFoundError(f"No background music files found in {BACKGROUND_MUSIC_DIRECTORY}")
    return background_music_files
