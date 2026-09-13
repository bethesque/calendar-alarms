from dataclasses import dataclass, field
import logging
import time
from homeaudio.audio.mpd import fade_up, mpd_connection
from homeaudio.audio.sound import track_length
from homeaudio.audio.scene import SceneProtocol
from homeaudio.audio.settings import SnapcastSettings, MpdSettings
from homeaudio.audio.snapcast import snapserver_manager_for_env
from homeaudio.env import CALENDAR_DATA_DIRECTORY

logger = logging.getLogger(__name__)

@dataclass
class NotificationFiles:
    event_alarms_file: str | None = None
    event_announcements_file: str | None = None
    scheduled_announcements_files: list[str] = field(default_factory=list)

"""
Takes a list of CalenderDays and finds any alarms due within the given time window.
"""

def play_notifications(notification_files: NotificationFiles, scene: SceneProtocol):
    mpd_settings = MpdSettings()
    snapcast_settings = SnapcastSettings()
    snapserver_manager = snapserver_manager_for_env(snapcast_settings)
    areas = snapserver_manager.connected_player_areas()
    announcements_file = notification_files.event_announcements_file
    scheduled_announcements_files = notification_files.scheduled_announcements_files
    alarms_file = notification_files.event_alarms_file

    if announcements_file or scheduled_announcements_files:
        snapserver_manager.set_volumes("tts")

    # Only announcement
    if announcements_file and not alarms_file and not scheduled_announcements_files:
        scene.around_announcement(lambda: _play_event_announcement(announcements_file, mpd_settings), areas)
        return
    # Announcement and/or alarm
    scene.prepare_for_alarm(areas)

    if announcements_file:
        _play_event_announcement(announcements_file, mpd_settings)

    if scheduled_announcements_files:
        for file in scheduled_announcements_files:
            _play_event_announcement(file, mpd_settings)

    if alarms_file:
        if announcements_file or scheduled_announcements_files:
            time.sleep(2)
        snapserver_manager.set_volumes("alarm")
        _play_event_alarm(alarms_file, mpd_settings)

def _play_event_announcement(announcements_file, mpd_settings):
    with mpd_connection(mpd_settings) as mpd:
        logger.info(f"Playing announcements {announcements_file}")
        mpd.set_volume(mpd_settings.volumes.tts)
        mpd.play_file(announcements_file)
    time.sleep(track_length(announcements_file))

def _play_event_alarm(alarms_file, mpd_settings: MpdSettings):
    with mpd_connection(mpd_settings) as mpd:
        fade_up_duration = 45
        logger.info(f"Playing alarm {alarms_file}, increasing volume from {mpd_settings.volumes.alarm_start} to {mpd_settings.volumes.alarm_end} over {fade_up_duration} seconds")
        mpd.set_volume(mpd_settings.volumes.alarm_start)
        mpd.play_file(alarms_file)
        fade_up([(mpd, mpd_settings.volumes.alarm_end)], fade_up_duration, 10)

def play_file(file: str, mpd_settings: MpdSettings | None = None):
    mpd_settings = mpd_settings or MpdSettings()
    with mpd_connection(mpd_settings) as mpd:
        logger.info(f"Playing {file}")
        mpd.play_file(file)