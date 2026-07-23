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

SILENCE_5_SEC = "audio/silence_5s.mp3"
SILENCE_1_SEC = "audio/silence_1s.mp3"
SILENCE_HALF_SEC = "audio/silence_500ms.mp3"

PRE_ANNOUNCEMENT_BELL = AUDIO_DIRECTORY + "/tunetank.com_alert-positive-chime-melody-s16.wav"
from enum import Enum

logger = logging.getLogger(__name__)

class AnnouncementUsecase(Enum):
    TTS = 1
    TALKIE = 2


@dataclass(frozen=True)
class TextAnnouncementRequest:
    scene: SceneProtocol
    sound_effect: str | None = None
    player_names: list[str] | None = None
    message: str | None = None
    usecase: AnnouncementUsecase = AnnouncementUsecase.TTS

@dataclass(frozen=True)
class AudioFileAnnouncementRequest:
    audio_file: str
    scene: SceneProtocol
    sound_effect: str | None = None
    player_names: list[str] | None = None
    usecase: AnnouncementUsecase = AnnouncementUsecase.TALKIE

@dataclass(frozen=True)
class PlayableRequest:
    audio_files: list[str]
    scene: SceneProtocol
    usecase: AnnouncementUsecase
    player_names: list[str] | None = None


def play_announcement(request: TextAnnouncementRequest):
    playable_request = PlayableRequestBuilder().build_playable_request_for_text_announcement(request)
    _play_audio_files(playable_request)

def play_audio_file_as_announcement(request: AudioFileAnnouncementRequest):
    playable_request = PlayableRequestBuilder().build_playable_request_for_audio_file(request)
    _play_audio_files(playable_request)

def _play_audio_files(request: PlayableRequest):
    snapserver_manager = SnapserverManager(SnapcastSettings(), request.player_names)
    snapserver_manager.set_volumes(request.usecase.name.lower())

    def play():
        try:
            mpd_settings = MpdSettings()
            with mpd_connection(mpd_settings) as mpd_player:
                mpd_player.set_volume(mpd_settings.volumes[request.usecase.name.lower()])
                mpd_player.play_files(request.audio_files)
                time.sleep(sum(track_length(f) for f in request.audio_files))
                logger.info("Finished playing files")
        except Exception:
            logger.exception(f"Error playing announcement audio file(s) {request.audio_files}")

    request.scene.around_announcement(play, snapserver_manager.connected_player_areas())

def list_sound_effects()-> list[str]:
        return ["none", "random"] + sorted([os.path.basename(path) for path in SoundEffectSelector().get_options_source().get_options()])

class SoundEffectSelector:
    def __init__(self, directory: str = AUDIO_DIRECTORY + "/sound_effects", extensions: list[str] = [".mp3"]):
        self.options_source = FileListOptionsSource(directory=directory, extensions=extensions)

    def get_options_source(self):
        return self.options_source


    def get_sound_effect_file(self, sound_effect: str | None) -> str | None:
        if sound_effect == "random":
            selected = select_text(None, ANNOUNCEMENT_SOUND_EFFECT_PROBABILITY, self.options_source)
            if selected:
                logger.info(f"Selected random sound effect {selected}")
                return selected
            else:
                logger.info("Random selection returned no sound effect")
                return None
        elif sound_effect and sound_effect != "none":
            sound_effect_file_path = os.path.join(AUDIO_DIRECTORY, "sound_effects", sound_effect)
            if os.path.isfile(sound_effect_file_path):
                logger.info(f"Using specified sound effect {sound_effect_file_path}")
                return sound_effect_file_path
            else:
                logger.warning(f"Sound effect file {sound_effect_file_path} does not exist. Skipping sound effect.")
                return None
        else:
            logger.info("No sound effect specified")
            return None


class PlayableRequestBuilder:
    def __init__(self, sound_effect_selector: SoundEffectSelector = SoundEffectSelector()):
        self.sound_effect_selector = sound_effect_selector

    def build_playable_request_for_text_announcement(self, request: TextAnnouncementRequest) -> PlayableRequest:
        if not request.message:
            raise ValueError("AnnouncementRequest.message is required")

        audio_files = self._build_one_off_announcement_file(request.message, request.sound_effect)
        return PlayableRequest(
            audio_files=audio_files,
            scene=request.scene,
            usecase=request.usecase,
            player_names=request.player_names
        )

    def build_playable_request_for_audio_file(self, request: AudioFileAnnouncementRequest) -> PlayableRequest:
        normalized_audio_file = self._normalized_audio_file_path(request.audio_file)
        normalize_audio(request.audio_file, normalized_audio_file)
        pre_announce_files = self.get_pre_announcement_files(request.sound_effect)
        return PlayableRequest(
            audio_files=pre_announce_files + [normalized_audio_file],
            scene=request.scene,
            usecase=AnnouncementUsecase.TALKIE,
            player_names=request.player_names
        )


    def _build_one_off_announcement_file(self, message: str, sound_effect: str | None = None) -> list[str]:
        speech_file = text_to_voice_file(message)
        #announcement_file = OUTPUT_AUDIO_DIRECTORY + "/one_off_announcement.wav"
        files = self.get_pre_announcement_files(sound_effect) + [speech_file, SILENCE_1_SEC]
        return files
        #join_mp3s_to_wav(files, announcement_file)
        #return announcement_file

    def get_pre_announcement_files(self, sound_effect: str | None)-> list[str]:
        files = [PRE_ANNOUNCEMENT_BELL]

        sound_effect_file = self.sound_effect_selector.get_sound_effect_file(sound_effect)
        if sound_effect_file:
            files.append(sound_effect_file)
            files.append(SILENCE_HALF_SEC)

        return files

    def _normalized_audio_file_path(self, audio_file):
        normalized_file_path = os.path.splitext(audio_file)[0] + "_normalized" + os.path.splitext(audio_file)[1]
        return normalized_file_path

