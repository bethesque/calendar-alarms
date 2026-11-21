import logging
from pathlib import Path
import threading
import time

from homeaudio.doorbell import DOORBELLS_DIRECTORY, DOORBELLS_ALLOWED_EXTENSIONS
from homeaudio.audio.snapcast import snapserver_manager_for_env
from homeaudio.audio.mpd import mpd_connection
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.random_text import FileListOptionsSource, select_option_pseudorandomly
from homeaudio.audio.settings import Feature, HomeAssistantSettings, MpdSettings, SnapcastSettings
from homeaudio.audio.sound import track_length

logger = logging.getLogger(__name__)

def _play_wake_up_alarm_via_mpd(doorbell_file, mpd_settings: MpdSettings):
    snapserver_manager = snapserver_manager_for_env(SnapcastSettings(), Feature.DOORBELL)
    snapserver_manager.set_volumes("doorbell")

    ha_settings = HomeAssistantSettings()
    ha_settings.announcements.fade_down_duration = 0
    scene = scene_for_env(ha_settings)

    def play_doorbell():
        with mpd_connection(mpd_settings) as mpd:
            logger.info(f"Playing alarm {doorbell_file}")
            mpd.set_volume(mpd_settings.volumes.doorbell)
            mpd.play_file(doorbell_file)
        time.sleep(track_length(doorbell_file))

    scene.around_announcement(play_doorbell)


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
