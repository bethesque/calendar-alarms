import logging
import glob
from datetime import datetime
from ecal.alarms.mpd import fade_up, mpd_connection
from ecal.calendar.google_calendar import WeatherForecast, load_data_from_file
from ecal.alarms.text_to_voice import text_to_voice_file_daily_summary
from ecal.alarms.sound import build_announcement_audio
from ecal.random_text import select_text
from ecal.select_item import select_item_by_date
from ecal.env import DATA_DIRECTORY, CACHE_DIRECTORY, OUTPUT_AUDIO_DIRECTORY, INITIAL_VOLUME
from ecal.alarms import BACKGROUND_MUSIC_DIRECTORY

DATA_FILE = f"{DATA_DIRECTORY}/calendar.json"
SPEECH_FILE = CACHE_DIRECTORY + "/audio/daily_summary.mp3"
MIXED_FILE = f"{OUTPUT_AUDIO_DIRECTORY}/mixed6.wav"
SILENCE = "audio/silence_5s.mp3"
ANNOUNCEMENT_BACKGROUND_MUSIC = "audio/Daybreak.mp3"
MORNING_ANNOUNCEMENTS_PRELUDE_CHOICES = "morning_announcements_prelude_choices.txt"

logger = logging.getLogger(__name__)

"""
Top level entry point. Generate a summary of today's events, convert them to voice, and play them.
"""
def announce(calendar_file=DATA_FILE):
    speech_file = get_morning_announcements_audio_file(calendar_file)
    play_morning_announcements_audio_file(speech_file)

"""
Helper method to play the cached announcement speech audio file to avoid a round trip to the text-to-speech service.
"""
def play_morning_announcements_audio_file(speech_file=SPEECH_FILE):
    background_music_file = get_background_music_file()
    build_announcement_audio(
        speech_file=speech_file,
        music_file=background_music_file,
        output_file=MIXED_FILE
    )
    # Play the mixed audio file
    with mpd_connection() as alarm_player:
        alarm_player.set_volume(INITIAL_VOLUME)
        alarm_player.play_file(MIXED_FILE)
        fade_up([(alarm_player, 90)], 5, 10)

"""
Generate the voice file from the calendar events in the given file, and return the
path to the voice file.
"""
def get_morning_announcements_audio_file(calendar_file=DATA_FILE):
    speech_file = text_to_voice_file_daily_summary(get_morning_announcements_text(calendar_file))
    return speech_file

def get_morning_announcements_text(calendar_file=DATA_FILE):
    announcement = " ".join(build_sentences(get_events(calendar_file)))
    logger.info(f"Generated daily summary announcement: {announcement}")
    return announcement

def get_events(calendar_file=DATA_FILE):
    # Array of CalendarDay objects
    calendar_days = load_data_from_file(calendar_file)
    return calendar_days[0].all_events() if calendar_days else []

"""
Build a List of sentences to speak aloud from the given list of Events.
"""
def build_sentences(all_events):
    weather_forecast = get_weather_forecast(all_events)
    events = get_non_weather_forecast_events(all_events)

    sentences = ["Good morning!"]

    extra_text = select_text(None, 1, MORNING_ANNOUNCEMENTS_PRELUDE_CHOICES)
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
