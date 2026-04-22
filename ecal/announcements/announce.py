import logging
from ecal.alarms.mpd import MpdClient, mpd_connection
from ecal.calendar.google_calendar import WeatherForecast, load_data_from_file
from ecal.alarms.text_to_voice import text_to_voice_file_daily_summary
from ecal.env import DATA_DIRECTORY, CACHE_DIRECTORY, OUTPUT_AUDIO_DIRECTORY, MPD_HOST, MPD_PORT, INITIAL_VOLUME
from ecal.alarms.sound import build_announcement_audio


DATA_FILE = f"{DATA_DIRECTORY}/calendar.json"
SPEECH_FILE = CACHE_DIRECTORY + "/audio/daily_summary.mp3"
MIXED_FILE = f"{OUTPUT_AUDIO_DIRECTORY}/mixed6.wav"
SILENCE = "audio/silence_5s.mp3"
ANNOUNCEMENT_BACKGROUND_MUSIC = "audio/Daybreak.mp3"

logger = logging.getLogger(__name__)

"""
Top level entry point. Generate a summary of today's events, convert them to voice, and play them.
"""
def announce(calendar_file=DATA_FILE):
    speech_file = get_daily_summary_announcement(calendar_file)
    play_morning_summary_announcement(speech_file)

def play_morning_summary_announcement(speech_file=SPEECH_FILE):
    build_announcement_audio(
        speech_file=speech_file,
        music_file=ANNOUNCEMENT_BACKGROUND_MUSIC,
        output_file=MIXED_FILE
    )
    # Play the mixed audio file
    with mpd_connection() as alarm_player:
        alarm_player.set_volume(INITIAL_VOLUME)
        alarm_player.play_file(MIXED_FILE)

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
    speech_file = text_to_voice_file_daily_summary(announcement)
    #speech_file = "cache/audio/daily_summary.mp3"
    return speech_file

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
