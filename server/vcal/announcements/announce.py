import logging
import glob
import os
import time
from datetime import datetime
from vcal.snapserver import Snapserver
from vcal.scene import SceneProtocol
from vcal.alarms.mpd import fade_up, mpd_connection
from vcal.cal.google_calendar import WeatherForecast, load_data_from_file
from vcal.alarms.text_to_voice import text_to_voice_file_daily_summary, text_to_voice_file
from vcal.alarms.sound import mix_announcement_audio, track_length, join_mp3s_to_wav
from vcal.random_text import FileListOptionsSource, TextFileOptionsSource, ListOptionsSource, select_text
from vcal.select_item import select_item_by_date, select_option
from vcal.env import DATA_DIRECTORY, CACHE_DIRECTORY, ANNOUNCEMENT_SOUND_EFFECT_PROBABILITY
from vcal.alarms import BACKGROUND_MUSIC_DIRECTORY, AUDIO_DIRECTORY, OUTPUT_AUDIO_DIRECTORY
from vcal.settings import SnapcastSettings, MpdSettings, MorningAnnouncementsSettings
from vcal.housie_talkie.audio import normalize_audio

CALENDAR_FILE = f"{DATA_DIRECTORY}/calendar.json"
SPEECH_FILE = CACHE_DIRECTORY + "/audio/morning_annoucements_speech.mp3"
MORNING_ANNOUNCEMENTS_AUDIO_FILE = f"{OUTPUT_AUDIO_DIRECTORY}/morning_announcements.wav"
SILENCE_5_SEC = "audio/silence_5s.mp3"
SILENCE_1_SEC = "audio/silence_1s.mp3"
SILENCE_HALF_SEC = "audio/silence_500ms.mp3"
MORNING_ANNOUNCEMENTS_PRELUDE_CHOICES = "morning_announcements_prelude_choices.txt"
PRE_ANNOUNCEMENT_BELL = AUDIO_DIRECTORY + "/preannounce_0_3_vol.mp3"
from enum import Enum

logger = logging.getLogger(__name__)

class AnnouncementUsecase(Enum):
    TTS = 1
    TALKIE = 2

class MissingCalendarDataException(Exception):
    pass

def play_announcement(message: str, scene: SceneProtocol, sound_effect = None, player_names: list[str] = []):
    announcement_file = _build_one_off_announcement_file(message, sound_effect)
    play_audio_files([announcement_file], scene, AnnouncementUsecase.TTS, player_names)

def play_audio_file_as_announcement(audio_file, scene: SceneProtocol, sound_effect = None, player_names: list[str] = []):
    normalized_audio_file = _normalized_audio_file_path(audio_file)
    normalize_audio(audio_file, normalized_audio_file)
    pre_announce_files = get_pre_announcement_files(sound_effect)
    play_audio_files(pre_announce_files + [normalized_audio_file], scene, AnnouncementUsecase.TALKIE, player_names)

def play_audio_files(audio_files: list[str], scene: SceneProtocol, usecase: AnnouncementUsecase, player_names: list[str] = []):
    areas = _set_snapclient_volumes(usecase.name.lower(), player_names)

    def play():
        try:
            mpd_settings = MpdSettings()
            with mpd_connection() as alarm_player:
                alarm_player.set_volume(mpd_settings.volumes[usecase.name.lower()])
                alarm_player.play_files(audio_files)
                time.sleep(sum(track_length(f) for f in audio_files))
        except Exception:
            logger.exception(f"Error playing announcement audio file(s) {audio_files}")

    scene.around_announcement(play, areas)

def _set_snapclient_volumes(usecase: str, player_names: list | None = None) -> set[str]:
    """
    Set the volumes of the Snapcast clients to the appropriate levels for the given usecase.
    If player_names is provided, only those players will be adjusted. Otherwise, all connected players will be adjusted.
    Returns a set of areas containing that were adjusted.
    """

    snapcast_settings = SnapcastSettings()
    snapserver = Snapserver(snapcast_settings.snapserver_rpc_url())
    player_names = player_names or snapserver.connected_client_names()
    snapserver.set_volumes(snapcast_settings.volumes_for_players(player_names, usecase))
    return set([sc.area for sc in snapcast_settings.snapclients if sc.host in player_names and sc.area is not None])


def list_sound_effects()-> list[str]:
    return ["none", "random"] + sorted([os.path.basename(path) for path in sound_effects_options_source().get_options()])

def _build_one_off_announcement_file(message: str, sound_effect: str | None = None):
    speech_file = text_to_voice_file(message)
    announcement_file = OUTPUT_AUDIO_DIRECTORY + "/one_off_announcement.wav"
    files = get_pre_announcement_files(sound_effect) + [speech_file, SILENCE_1_SEC]
    join_mp3s_to_wav(files, announcement_file)
    return announcement_file

def get_pre_announcement_files(sound_effect: str | None)-> list[str]:
    files = [PRE_ANNOUNCEMENT_BELL]
    if sound_effect == "random":
        sound_effect = select_text(None, ANNOUNCEMENT_SOUND_EFFECT_PROBABILITY, sound_effects_options_source())
        if sound_effect:
            logger.info(f"Selected random sound effect {sound_effect}")
            files.append(sound_effect)
            files.append(SILENCE_HALF_SEC)
        else:
            logger.info("Random selection returned no sound effect")
    elif sound_effect and sound_effect != "none":
        sound_effect_file_path = os.path.join(AUDIO_DIRECTORY, "sound_effects", sound_effect)
        if os.path.isfile(sound_effect_file_path):
            logger.info(f"Using specified sound effect {sound_effect_file_path}")
            files.append(sound_effect_file_path)
            files.append(SILENCE_HALF_SEC)
        else:
            logger.warning(f"Sound effect file {sound_effect_file_path} does not exist. Skipping sound effect.")
    else:
        logger.info("No sound effect specified")

    return files

def sound_effects_options_source() -> FileListOptionsSource:
    return FileListOptionsSource(directory=AUDIO_DIRECTORY + "/sound_effects", extensions=[".mp3"])

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

    _set_snapclient_volumes("tts", None)

    before_announcement_hook() if before_announcement_hook else None

    # Play the mixed audio file
    with mpd_connection() as alarm_player:
        volumes = MpdSettings().volumes
        alarm_player.set_volume(volumes.alarm_start)
        alarm_player.play_file(audio_file)
        fade_up([(alarm_player, volumes.tts)], 5, 10)

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

    prelude = get_prelude()
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

    sentences.extend(get_postlude())

    sentences.append("Have a lovely day.")

    return sentences

def get_prelude()-> str | None:
    settings = MorningAnnouncementsSettings()
    prelude_options = ListOptionsSource("MorningAnnouncementsSettings.prelude_options", settings.prelude_options)
    return select_text(None, settings.prelude_probability, prelude_options)

def get_postlude()-> list[str]:
    settings = MorningAnnouncementsSettings()
    unused_facts = settings.unused_facts
    if unused_facts:
        fact_text = select_option(unused_facts).text
        settings.save()  # Save the updated last_used timestamps for the selected facts
        return [f"Your fun fact for today is:", fact_text]
    else:
        logger.info("All facts have been used.")
        return []

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

def _normalized_audio_file_path(audio_file):
    normalized_file_path = os.path.splitext(audio_file)[0] + "_normalized" + os.path.splitext(audio_file)[1]
    return normalized_file_path
