import logging
import glob
import os
import time
from dataclasses import dataclass
from datetime import datetime

from vcal.scene import SceneProtocol
from vcal.alarms.mpd import fade_up, mpd_connection
from vcal.cal.google_calendar import load_data_from_file
from vcal.alarms.text_to_voice import text_to_voice_file
from vcal.alarms.sound import track_length, join_mp3s_to_wav
from vcal.random_text import FileListOptionsSource, select_text
from vcal.env import DATA_DIRECTORY, ANNOUNCEMENT_SOUND_EFFECT_PROBABILITY
from vcal.alarms import  AUDIO_DIRECTORY, OUTPUT_AUDIO_DIRECTORY
from vcal.settings import SnapcastSettings, MpdSettings
from vcal.announcements.snapcast import SnapserverManager
from vcal.housie_talkie.audio import normalize_audio

CALENDAR_FILE = f"{DATA_DIRECTORY}/calendar.json"

SILENCE_5_SEC = "audio/silence_5s.mp3"
SILENCE_1_SEC = "audio/silence_1s.mp3"
SILENCE_HALF_SEC = "audio/silence_500ms.mp3"

PRE_ANNOUNCEMENT_BELL = AUDIO_DIRECTORY + "/preannounce_3.mp3"
from enum import Enum

logger = logging.getLogger(__name__)

class AnnouncementUsecase(Enum):
    TTS = 1
    TALKIE = 2


@dataclass(frozen=True)
class AnnouncementRequest:
    scene: SceneProtocol
    sound_effect: str | None = None
    player_names: list[str] | None = None
    message: str | None = None
    usecase: AnnouncementUsecase = AnnouncementUsecase.TTS



def play_announcement(request: AnnouncementRequest):
    if not request.message:
        raise ValueError("AnnouncementRequest.message is required")

    announcement_file = _build_one_off_announcement_file(request.message, request.sound_effect)
    _play_audio_files([announcement_file], request.scene, request.usecase, request.player_names)

def play_audio_file_as_announcement(audio_file, scene: SceneProtocol, sound_effect = None, player_names: list[str] | None = None):
    normalized_audio_file = _normalized_audio_file_path(audio_file)
    normalize_audio(audio_file, normalized_audio_file)
    pre_announce_files = get_pre_announcement_files(sound_effect)
    _play_audio_files(pre_announce_files + [normalized_audio_file], scene, AnnouncementUsecase.TALKIE, player_names)

def _play_audio_files(audio_files: list[str], scene: SceneProtocol, usecase: AnnouncementUsecase, player_names: list[str] | None = None):
    areas = SnapserverManager(SnapcastSettings()).set_volumes(usecase.name.lower(), player_names)

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

def _normalized_audio_file_path(audio_file):
    normalized_file_path = os.path.splitext(audio_file)[0] + "_normalized" + os.path.splitext(audio_file)[1]
    return normalized_file_path
