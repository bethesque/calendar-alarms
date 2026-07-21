import logging
import glob
import time
from datetime import timedelta
from vcal.cal.google_calendar import EventNotification, NotificationType
from vcal.alarms.sound import build_alarm_audio, join_mp3s_to_wav
from vcal.alarms.text_to_voice import text_to_voice_file
from vcal.alarms.mpd import fade_up, fade_out, mpd_connection
from vcal.select_item import select_item_by_date
from vcal.alarms import ALARMS_DIRECTORY, AUDIO_DIRECTORY, OUTPUT_AUDIO_DIRECTORY
from vcal.alarms.sound import track_length
from vcal.scene import SceneProtocol
from vcal.settings import SnapcastSettings, MpdSettings, GoogleCalendarSettings
from vcal.snapserver import Snapserver
from vcal.announcements.snapcast import SnapserverManager

logger = logging.getLogger(__name__)

"""
Takes a list of CalenderDays and finds any alarms due within the given time window.
"""

class NotificationFinder:
    def __init__(self, calendar_days, base_time, window, notification_rules=None):
        self.calendar_days = calendar_days
        self.base_time = base_time
        self.window = window
        self.notification_rules = notification_rules or []


    def find_notification_events(self):
        start, end = self._get_time_window()

        matching_events = []

        for day in self.calendar_days:
            for event in day.timed_events:
                event_notifications = event.notifications_within_window(start, end, self.notification_rules)
                matching_events.extend(event_notifications)

        self._log_results(start, end, matching_events)

        return matching_events


    def _get_time_window(self):
        # Round down to nearest multiple of WINDOW
        minute = (self.base_time.minute // self.window) * self.window
        start_time = self.base_time.replace(minute=minute, second=0, microsecond=0)
        end_time = start_time + timedelta(minutes=self.window)
        return start_time, end_time

    def _log_results(self, start, end, results:list[EventNotification]):
        logging.info(
            "Time window: %s → %s (WINDOW=%d mins)",
            start.isoformat(),
            end.isoformat(),
            self.window)

        for event_notification in results:
            logging.info(
                "Matched event: %s | %s with %s offset by %d mins at %s)",
                event_notification.event.start_time,
                event_notification.event.summary,
                event_notification.type.name.lower(),
                event_notification.offset,
                event_notification.notification_time
            )
        logging.info("Total matched events: %d", len(results))
        return results

"""
Builds the alarm audio by using TTS to read out the event descriptions, and
mixing in background alarm music.
"""
class AlarmAudio:
    def __init__(self, event_notifications: list[EventNotification], base_time):
        self.event_notifications = event_notifications
        self.base_time = base_time

    def build_alarm_file(self):
        joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/alarm.wav"
        join_mp3s_to_wav(self._announcement_files_for_events(), joined_announcement_file)

        audio_file = OUTPUT_AUDIO_DIRECTORY + "/alarm_mixed.wav"

        alarm_file = self._get_alarm_file()

        build_alarm_audio(
            announcement_file=joined_announcement_file,
            alarm_file=alarm_file,
            output_file=audio_file,
            duration=300
        )
        return audio_file

    def _announcement_files_for_events(self):
        return self._deduplicate_list([text_to_voice_file(self._announcement_for_event(event)) for event in self.event_notifications])

    def _announcement_for_event(self, event_notification: EventNotification):
        summary = event_notification.event.summary if event_notification.event.summary else "an event"
        if event_notification.offset > 0:
            return f"It will be time for {summary} in {event_notification.offset} minutes"
        else:
            return f"It's time for {summary}"

    def _get_alarm_file(self):
        alarm_files = self._get_alarm_files()
        # New alarm every 14 days
        return select_item_by_date(sorted(alarm_files), self.base_time.date(), 14)

    def _deduplicate_list(self, items):
        return list(dict.fromkeys(items))

    def _get_alarm_files(self):
        # Get all mp3 files in the ALARMS_DIRECTORY
        alarm_files = glob.glob(f"{ALARMS_DIRECTORY}/*.mp3")
        if not alarm_files:
            raise FileNotFoundError(f"No alarm files found in {ALARMS_DIRECTORY}")
        return alarm_files


"""
Builds the alarm audio by using TTS to read out the event descriptions, and
mixing in background alarm music.
"""
class AnnouncementAudio:
    def __init__(self, event_notifications: list[EventNotification], base_time):
        self.event_notifications = event_notifications
        self.base_time = base_time

    def build_announcement_file(self):
        joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/announcement.wav"
        files = [self.preannouncement_bell()] + self._announcement_files_for_events()
        join_mp3s_to_wav(files, joined_announcement_file)

        return joined_announcement_file

    def _announcement_files_for_events(self):
        return self._deduplicate_list([text_to_voice_file(self._announcement_for_event(event)) for event in self.event_notifications])

    def _announcement_for_event(self, event_notification: EventNotification):
        summary = event_notification.event.summary if event_notification.event.summary else "an event"
        if event_notification.offset > 0:
            return f"It will be time for {summary} in {event_notification.offset} minutes"
        else:
            return f"It's time for {summary}"

    def _deduplicate_list(self, items):
        return list(dict.fromkeys(items))

    def preannouncement_bell(self):
        return AUDIO_DIRECTORY + "/preannounce_3.mp3"

def play_notifications(announcements_file: str, alarms_file: str, scene: SceneProtocol):
    mpd_settings = MpdSettings()
    snapcast_settings = SnapcastSettings()
    snapserver_manager = SnapserverManager(snapcast_settings)
    areas = snapserver_manager.connected_player_areas()

    if announcements_file:
        snapserver_manager.set_volumes("tts")

    # Only announcement
    if announcements_file and not alarms_file:
        scene.around_announcement(lambda: _play_announcement(announcements_file, mpd_settings), areas)
        return

    # Announcement and/or alarm
    scene.prepare_for_alarm(areas)
    if announcements_file:
        _play_announcement(announcements_file, mpd_settings)

    if announcements_file and alarms_file:
        time.sleep(2)

    if alarms_file:
        snapserver_manager.set_volumes("alarm")
        _play_alarm(alarms_file, mpd_settings)

def _play_announcement(announcements_file, mpd_settings):
    with mpd_connection(mpd_settings) as alarm_player:

        logger.info(f"Playing announcements {announcements_file}")
        alarm_player.set_volume(mpd_settings.volumes.tts)
        alarm_player.play_file(announcements_file)
    time.sleep(track_length(announcements_file))

def _play_alarm(alarms_file, mpd_settings: MpdSettings):
    with mpd_connection(mpd_settings) as alarm_player:
        fade_up_duration = 45
        logger.info(f"Playing alarm {alarms_file}, increasing volume from {mpd_settings.volumes.alarm_start} to {mpd_settings.volumes.alarm_end} over {fade_up_duration} seconds")
        alarm_player.set_volume(mpd_settings.volumes.alarm_start)
        alarm_player.play_file(alarms_file)
        fade_up([(alarm_player, mpd_settings.volumes.alarm_end)], fade_up_duration, 10)

def stop_alarm(after_alarm_hook=None):
    # Stop alarm
    logger.info("Stopping alarm...")
    message = ""
    try:
        with mpd_connection() as alarm_player:
            if alarm_player.is_running():
                fade_out([alarm_player], 1, 5)
                alarm_player.stop()
                message = "Alarm stopped."
            else:
                message = "MPD is not running. No alarm to stop."
    except Exception as e:
        logger.error(f"Error stopping alarm: {e}")

    logger.info(message)

    after_alarm_hook() if after_alarm_hook else None

def check_for_notifications(base_time, window, calendar_data, scene:SceneProtocol):
    notification_rules = GoogleCalendarSettings().notification_rules
    alarm_finder = NotificationFinder(calendar_data, base_time, window, notification_rules)
    event_notifications = alarm_finder.find_notification_events()

    if event_notifications:
        # Separate alarm and announcement notifications
        alarm_event_notifications = [event for event in event_notifications if event.type == NotificationType.ALARM]
        announcement_event_notifications = [event for event in event_notifications if event.type == NotificationType.ANNOUNCE]

        alarm_audio_file = AlarmAudio(alarm_event_notifications, base_time).build_alarm_file() if alarm_event_notifications else None
        announcements_file = AnnouncementAudio(announcement_event_notifications, base_time).build_announcement_file() if announcement_event_notifications else None
        play_notifications(announcements_file, alarm_audio_file, scene)

