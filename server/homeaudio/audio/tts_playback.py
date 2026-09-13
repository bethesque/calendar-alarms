import time
import logging
from homeaudio.audio.mpd import fade_up, mpd_connection
from homeaudio.audio.snapcast import snapserver_manager_for_env
from homeaudio.audio.settings import MpdSettings, SnapcastSettings
from homeaudio.audio.sound import track_length

logger = logging.getLogger(__name__)

"""
Plays a TTS audio file at the configured "tts" volume, running optional hooks before playback
starts and after it finishes. Shared by any feature that plays a one-off TTS announcement
through MPD/Snapcast (morning announcements, school announcements, ...).
"""
def play_tts_audio_file(audio_file, snapcast_settings: SnapcastSettings, mpd_settings: MpdSettings, before_announcement_hook=None, after_announcement_hook=None):

    try:
        snapserver_manager_for_env(snapcast_settings).set_volumes("tts")
    except Exception:
        logger.exception("Could not set Snapcast volumes. Audio may not be heard.")

    before_announcement_hook() if before_announcement_hook else None

    with mpd_connection(mpd_settings) as alarm_player:
        volumes = mpd_settings.volumes
        alarm_player.set_volume(volumes.tts)
        alarm_player.play_file(audio_file)

    if after_announcement_hook:
        time.sleep(track_length(audio_file))
        after_announcement_hook()
