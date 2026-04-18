import logging
from ecal.google_calendar import WeatherForecast, load_data_from_file
from ecal.alarms.text_to_voice import text_to_voice_file_daily_summary
from ecal.env import DATA_DIRECTORY, CACHE_DIRECTORY
from ecal.alarms import DEFAULT_VOLUME
from ecal.log_config import setup_logging
from ecal.alarms.alarm import prepare_mvp_processes

DATA_FILE = f"{DATA_DIRECTORY}/calendar.json"
ANNOUNCEMENT_FILE = CACHE_DIRECTORY + "/audio/daily_summary.mp3"
SILENCE = "audio/silence_5s.mp3"
ANNOUNCEMENT_BACKGROUND_MUSIC = "audio/Daybreak.mp3"

setup_logging(logging.INFO)

logger = logging.getLogger(__name__)

"""
Top level entry point. Generate a summary of today's events, convert them to voice, and play them.
"""
def announce(calendar_file=DATA_FILE):
    announcement_file = get_daily_summary_announcement(calendar_file)
    play_morning_summary_announcement(announcement_file)

def play_morning_summary_announcement(announcement_file=ANNOUNCEMENT_FILE):
    alarm_process, announcement_process = prepare_mvp_processes()
    alarm_process.set_volume(DEFAULT_VOLUME * .60)
    alarm_process.play_file(ANNOUNCEMENT_BACKGROUND_MUSIC)
    announcement_process.play_files([SILENCE, announcement_file])

"""
Generate the voice file from the calendar events in the given file, and return the
path to the voice file.
"""
def get_daily_summary_announcement(calendar_file=DATA_FILE):
    # Array of CalendarDay objects
    calendar_days = load_data_from_file(calendar_file)
    all_events = calendar_days[0].all_events() if calendar_days else []
    sentences = build_sentences(all_events)
    announcement = " ".join(sentences)
    logger.info(f"Generated daily summary announcement: {announcement}")
    announcement_file = text_to_voice_file_daily_summary(announcement)
    #announcement_file = "cache/audio/daily_summary.mp3"
    return announcement_file

"""
Build a List of sentences to speak aloud from the given list of Events.
"""
def build_sentences(all_events):
    weather_forecast = get_weather_forecast(all_events)
    events = get_non_weather_forecast_events(all_events)

    sentences = ["Good morning!"]

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
