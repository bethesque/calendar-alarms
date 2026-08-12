import logging
from enum import Enum
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from vcal.scene import SceneProtocol
from vcal.notifications.text_to_voice import text_to_voice_file
from vcal.notifications.sound import track_length, join_mp3s_to_wav, join_mixed_files_to_wav
from vcal.notifications import  AUDIO_DIRECTORY, OUTPUT_AUDIO_DIRECTORY
from vcal.env import ANNOUNCEMENT_SOUND_EFFECT_PROBABILITY
from vcal.random_text import FileListOptionsSource, select_text

logger = logging.getLogger(__name__)

# ffmpeg -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t 0.25 -q:a 9 -acodec libmp3lame silence.mp3

SILENCE_5_SEC = "audio/silence_5s.mp3"
SILENCE_1_SEC = "audio/silence_1s.mp3"
SILENCE_HALF_SEC = "audio/silence_500ms.mp3"
SILENCE_QUARTER_SEC = "audio/silence_250ms.mp3"
POST_ANNOUNCEMENT_SILENCE = SILENCE_QUARTER_SEC

PRE_ANNOUNCEMENT_BELL = AUDIO_DIRECTORY + "/preannounce_4.mp3"

class AnnouncementUsecase(Enum):
    TTS = 1
    VOICE = 2

@dataclass(frozen=True)
class TtsAnnouncementRequest:
    scene: SceneProtocol
    sound_effect: str | None = None
    player_names: list[str] | None = None
    message: str | None = None
    usecase: AnnouncementUsecase = AnnouncementUsecase.TTS

@dataclass(frozen=True)
class VoiceAnnouncementRequest:
    audio_file: str
    scene: SceneProtocol
    sound_effect: str | None = None
    player_names: list[str] | None = None
    usecase: AnnouncementUsecase = AnnouncementUsecase.VOICE

@dataclass(frozen=True)
class PlayableRequest:
    audio_files: list[str]
    scene: SceneProtocol
    usecase: AnnouncementUsecase
    player_names: list[str] | None = None

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

    def build_playable_request_for_tts_announcement(self, request: TtsAnnouncementRequest) -> PlayableRequest:
        if not request.message:
            raise ValueError("AnnouncementRequest.message is required")

        audio_file = self._build_one_off_announcement_file(request.message, request.sound_effect)
        return PlayableRequest(
            audio_files=[audio_file],
            scene=request.scene,
            usecase=request.usecase,
            player_names=request.player_names
        )

    def build_playable_request_for_voice_announcement(self, request: VoiceAnnouncementRequest) -> PlayableRequest:
        announcement_file = OUTPUT_AUDIO_DIRECTORY +  f"/{Path(request.audio_file).stem}_" + self._datestamp() + ".wav"
        mp3_files = self.get_pre_announcement_files(request.sound_effect) + [request.audio_file, POST_ANNOUNCEMENT_SILENCE]
        join_mixed_files_to_wav(mp3_files, announcement_file)
        return PlayableRequest(
            audio_files=[announcement_file],
            scene=request.scene,
            usecase=AnnouncementUsecase.VOICE,
            player_names=request.player_names
        )

    def _build_one_off_announcement_file(self, message: str, sound_effect: str | None = None):
        speech_file = text_to_voice_file(message)
        announcement_file = OUTPUT_AUDIO_DIRECTORY + "/tts_" + self._datestamp() + ".wav"
        mp3_files = self.get_pre_announcement_files(sound_effect) + [speech_file, POST_ANNOUNCEMENT_SILENCE]
        join_mp3s_to_wav(mp3_files, announcement_file)
        return announcement_file

    def get_pre_announcement_files(self, sound_effect: str | None)-> list[str]:
        files = [PRE_ANNOUNCEMENT_BELL]

        sound_effect_file = self.sound_effect_selector.get_sound_effect_file(sound_effect)
        if sound_effect_file:
            files.append(sound_effect_file)
            files.append(SILENCE_HALF_SEC)

        return files

    def _datestamp(self) -> str:
        now = datetime.now()
        return f"{now.strftime('%y%m%d%H%M%S')}{now.microsecond // 1000:03d}"