import logging
import os
from enum import Enum
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from homeaudio.audio.scene import SceneProtocol
from homeaudio.vcal.notifications.text_to_voice import text_to_voice_file
from homeaudio.audio.sound import join_mp3s_to_wav, join_mixed_files_to_wav
from homeaudio.vcal.notifications import OUTPUT_AUDIO_DIRECTORY, PRE_ANNOUNCEMENT_BELL, POST_ANNOUNCEMENT_SILENCE, SILENCE_HALF_SEC
from homeaudio.audio.sound_effects import SoundEffectSelector

logger = logging.getLogger(__name__)

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

class PlayableRequestBuilder:
    def __init__(self, sound_effect_selector: SoundEffectSelector):
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