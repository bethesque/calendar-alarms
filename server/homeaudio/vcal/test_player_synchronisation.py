import logging
from pathlib import Path
import threading

from homeaudio.audio.snapcast import snapserver_manager_for_env
from homeaudio.audio.mpd import mpd_connection
from homeaudio.audio.settings import MpdSettings, SnapcastSettings

logger = logging.getLogger(__name__)

METRONOME_FILE = str(Path("audio_resources/reycophoto-metronome-1-164214.mp3").absolute())

def _play_metronome_via_mpd(audio_file, mpd_settings: MpdSettings):
    snapserver_manager = snapserver_manager_for_env(SnapcastSettings())
    snapserver_manager.set_volumes("alarm")

    with mpd_connection(mpd_settings) as mpd:
        logger.info(f"Playing metronome file {audio_file}")
        mpd.set_volume(int((mpd_settings.volumes.alarm_end + mpd_settings.volumes.alarm_start)/2))
        mpd.play_file(audio_file)


def start_metronome():
    threading.Thread(
            target=_play_metronome_via_mpd,
            args=(METRONOME_FILE, MpdSettings()),
            daemon=True,
        ).start()
    return Path(METRONOME_FILE).name
