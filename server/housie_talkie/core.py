import logging
import os
import time

from vcal.notifications.mpd import mpd_connection
from vcal.notifications import  AUDIO_DIRECTORY, OUTPUT_AUDIO_DIRECTORY
from vcal.settings import SnapcastSettings, MpdSettings
from vcal.snapcast import SnapserverManager
from housie_talkie.models import *

logger = logging.getLogger(__name__)

def play_tts_announcement(request: TtsAnnouncementRequest):
    playable_request = PlayableRequestBuilder().build_playable_request_for_tts_announcement(request)
    _play_audio_files(playable_request)

def play_voice_announcement(request: VoiceAnnouncementRequest):
    playable_request = PlayableRequestBuilder().build_playable_request_for_voice_announcement(request)
    _play_audio_files(playable_request)

def _play_audio_files(request: PlayableRequest):
    snapserver_manager = SnapserverManager(SnapcastSettings(), request.player_names)
    snapserver_manager.set_volumes(request.usecase.name.lower())

    def play():
        try:
            mpd_settings = MpdSettings()
            with mpd_connection(mpd_settings) as alarm_player:
                alarm_player.set_volume(mpd_settings.volumes[request.usecase.name.lower()])
                alarm_player.play_files(request.audio_files)
                time.sleep(sum(track_length(f) for f in request.audio_files))
                logger.info("Finished playing files")
        except Exception:
            logger.exception(f"Error playing announcement audio file(s) {request.audio_files}")

    request.scene.around_announcement(play, snapserver_manager.connected_player_areas())

def list_sound_effects()-> list[str]:
        return ["none", "random"] + sorted([os.path.basename(path) for path in SoundEffectSelector().get_options_source().get_options()])







