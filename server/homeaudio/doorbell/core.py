import logging
from pathlib import Path
import threading

from homeaudio.doorbell import DOORBELLS_DIRECTORY, DOORBELLS_ALLOWED_EXTENSIONS
from homeaudio.audio.snapcast import snapserver_manager_for_env
from homeaudio.audio.mpd import mpd_connection
from homeaudio.audio.random_text import FileListOptionsSource, select_option_pseudorandomly
from homeaudio.audio.settings import Feature, MpdSettings, SnapcastSettings

logger = logging.getLogger(__name__)

def _play_wake_up_alarm_via_mpd(doorbell_file, mpd_settings: MpdSettings):
    snapserver_manager = snapserver_manager_for_env(SnapcastSettings(), Feature.DOORBELL)
    snapserver_manager.set_volumes("doorbell")

    with mpd_connection(mpd_settings) as mpd:
        logger.info(f"Playing alarm {doorbell_file}")
        mpd.set_volume(mpd_settings.volumes.doorbell)
        mpd.play_file(doorbell_file)


def start_doorbell():
    selected_alarm = select_option_pseudorandomly(None, 1, FileListOptionsSource(directory=str(DOORBELLS_DIRECTORY), extensions=sorted(DOORBELLS_ALLOWED_EXTENSIONS)))
    if selected_alarm:
        threading.Thread(
                target=_play_wake_up_alarm_via_mpd,
                args=(selected_alarm, MpdSettings()),
                daemon=True,
            ).start()
        return (True, Path(selected_alarm).name)
    else:
        return (False, "No doorbells found")
