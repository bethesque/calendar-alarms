import logging
from pathlib import Path
import threading

from vcal.snapcast import SnapserverManager
from vcal.notifications.mpd import fade_up, mpd_connection
from vcal.random_text import FileListOptionsSource, select_text
from vcal.settings import MpdSettings, SnapcastSettings
from vcal.env import WAKE_UP_ALARMS_DIRECTORY

logger = logging.getLogger(__name__)

def _play_wake_up_alarm_via_mpd(alarm_file, mpd_settings: MpdSettings):
    fade_up_duration = 30
    alarm_start_volume = 0
    alarm_end_volume = mpd_settings.volumes.wake_up_alarm_end
    steps = 10

    snapserver_manager = SnapserverManager(SnapcastSettings())
    snapserver_manager.set_volumes("alarm")

    with mpd_connection(mpd_settings) as mpd:
        logger.info(f"Playing alarm {alarm_file}, increasing volume from {alarm_start_volume} to {alarm_end_volume} over {fade_up_duration} seconds")
        mpd.set_volume(0)
        mpd.play_file(alarm_file)
        fade_up([(mpd, alarm_end_volume)], fade_up_duration, steps)


def start_wake_up_alarm():
    selected_alarm = select_text(None, 1, FileListOptionsSource(directory=WAKE_UP_ALARMS_DIRECTORY, extensions=["mp3"]))
    if selected_alarm:
        threading.Thread(
                target=_play_wake_up_alarm_via_mpd,
                args=(selected_alarm, MpdSettings()),
                daemon=True,
            ).start()
        return (True, Path(selected_alarm).name)
    else:
        return (False, "No alarms found")

