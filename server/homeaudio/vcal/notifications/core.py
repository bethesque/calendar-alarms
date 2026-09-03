import logging
import time
from datetime import datetime, timedelta
from homeaudio.vcal.cal.google_calendar import CalendarDay, EventNotification, NotificationType, CalendarSource
from homeaudio.audio.sound import join_mp3s_to_wav
from homeaudio.vcal.notifications.text_to_voice import text_to_voice_file
from homeaudio.audio.mpd import fade_out, fade_up, mpd_connection
from homeaudio.vcal.notifications import OUTPUT_AUDIO_DIRECTORY, POST_ANNOUNCEMENT_SILENCE
from homeaudio.audio.sound import track_length
from homeaudio.audio.scene import NullScene, SceneProtocol, HomeAssistantScene
from homeaudio.audio.settings import SnapcastSettings, MpdSettings, EventNotificationSettings
from homeaudio.audio.snapcast import SnapserverManager
from homeaudio.audio.snapserver import Snapserver
from homeaudio.housie_talkie.models import SoundEffectSelector
from homeaudio.vcal.notifications.audio import AlarmAudio, AnnouncementAudio
from homeaudio.vcal.notifications.text import NotificationTextBuilder
from homeaudio.vcal.notifications.snooze import LastPlayedState, SnoozeState, due_snoozed_event_notifications
from homeaudio.env import CALENDAR_DATA_DIRECTORY

logger = logging.getLogger(__name__)

DATA_FILE = CALENDAR_DATA_DIRECTORY + "/calendar.json"


"""
Takes a list of CalenderDays and finds any alarms due within the given time window.
"""

class NotificationFinder:
    def __init__(self, calendar_days: list[CalendarDay], base_time, window, notification_rules=None):
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
        logger.info(
            "Time window: %s → %s (WINDOW=%d mins)",
            start.isoformat(),
            end.isoformat(),
            self.window)

        for event_notification in results:
            logger.info(
                "Matched event: %s | %s with %s offset by %d mins at %s)",
                event_notification.event.start_time,
                event_notification.event.summary,
                event_notification.type.name.lower(),
                event_notification.offset,
                event_notification.notification_time
            )
        logger.info("Total matched events: %d", len(results))
        return results



def play_notifications(announcements_file: str | None, alarms_file: str | None, scene: SceneProtocol):
    mpd_settings = MpdSettings()
    snapcast_settings = SnapcastSettings()
    snapserver_manager = SnapserverManager(snapcast_settings)
    areas = snapserver_manager.connected_player_areas()

    if announcements_file:
        snapserver_manager.set_volumes("tts")

    # Only announcement
    if announcements_file and not alarms_file:
        scene.around_announcement(lambda: _play_event_announcement(announcements_file, mpd_settings), areas)
        return

    # Announcement and/or alarm
    scene.prepare_for_alarm(areas)
    if announcements_file:
        _play_event_announcement(announcements_file, mpd_settings)

    if announcements_file and alarms_file:
        time.sleep(2)

    if alarms_file:
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

def stop_alarm(after_alarm_hook=None):
    # Stop alarm
    logger.info("Stopping alarm...")
    message = ""
    try:
        with mpd_connection() as mpd:
            if mpd.is_running():
                #mpd.set_volume(0)
                #fade_out([alarm_player], 1, 5)
                # If any HousieTalkie files have been added while notification is playing,
                # play them next.
                # If no other files have been added, it will just stop playback
                mpd.next()
                message = "Alarm stopped."
            else:
                message = "MPD is not running. No alarm to stop."
    except Exception as e:
        logger.error(f"Error stopping alarm: {e}")

    logger.info(message)

    after_alarm_hook() if after_alarm_hook else None

def snooze_alarm(after_alarm_hook=None):
    logger.info("Snoozing alarm")
    stop_alarm(None)

    last_played = LastPlayedState()
    if not last_played.fresh():
        _play_file(_build_one_off_announcement_file("Nothing to snooze"))
        return

    event_notifications = last_played.load()
    base_time = last_played.load_base_time()

    if not event_notifications or not base_time:
        _play_file(_build_one_off_announcement_file("Nothing to snooze"))
        return

    snooze_minutes = EventNotificationSettings().snooze_minutes
    replay_at = base_time + timedelta(minutes=snooze_minutes)
    actual_snooze_minutes = int((replay_at - datetime.now().astimezone()).total_seconds() // 60)
    SnoozeState().save(event_notifications, replay_at)
    logger.info(f"Snoozed last alarm for {actual_snooze_minutes} minutes until {replay_at}")
    _play_file(_build_one_off_announcement_file(f"Snoozing for {actual_snooze_minutes} minutes"))

    if after_alarm_hook:
        after_alarm_hook()

def _play_file(file: str, mpd_settings: MpdSettings = MpdSettings()):
    with mpd_connection(mpd_settings) as mpd:
        logger.info(f"Playing {file}")
        mpd.play_file(file)

def _build_one_off_announcement_file(message: str):
    speech_file = text_to_voice_file(message)
    announcement_file = OUTPUT_AUDIO_DIRECTORY + "/tts_" + _datestamp() + ".wav"
    join_mp3s_to_wav([speech_file, POST_ANNOUNCEMENT_SILENCE], announcement_file)
    return announcement_file

def _datestamp() -> str:
    now = datetime.now()
    return f"{now.strftime('%y%m%d%H%M%S')}{now.microsecond // 1000:03d}"

def replay_last_notification(mpd_settings: MpdSettings = MpdSettings()):
    with mpd_connection() as mpd:
        mpd.set_volume(mpd_settings.volumes.tts)
        mpd.play()

# TODO mute Music Assistant also
def mute_alarm_for_area_of_player(player, snapcast_settings: SnapcastSettings = SnapcastSettings()):
    area = snapcast_settings.snapclient_settings(player).area
    if area:
        names = [ snapclient.name for snapclient in snapcast_settings.snapclients_for_area(area)]
        snapserver = Snapserver(snapcast_settings.snapserver_rpc_url)
        snapserver.mute_clients(names)
    else:
        logger.info(f"No area found for player {player}, cannot mute area")

def test_alarm():
    now = datetime.now().astimezone()

    days = [
        {
            "date":  now.strftime("%Y-%m-%d"),
            "date_time": now.isoformat(),
            "timed_events": [
                {
                    "description": "#alarm",
                    "end_time": None,
                    "owner": "Beth",
                    "calendar_id": "id",
                    "recurring": False,
                    "start_time": now.isoformat(),
                    "summary": "test the alarm"
                },
            ],
            "whole_day_events": []
        }
    ]

    calendar_data = CalendarSource(cache_file_path="").load_data_from_any(days)

    check_for_notifications(now, 5, calendar_data, HomeAssistantScene())


def check_for_notifications(base_time, window, calendar_days: list[CalendarDay], scene:SceneProtocol, event_notification_settings: EventNotificationSettings = EventNotificationSettings()):
    event_notifications = get_event_notifications(base_time, window, calendar_days, event_notification_settings)
    event_notifications = event_notifications + due_snoozed_event_notifications(base_time)

    build_and_play_notifications(event_notifications, base_time, scene, event_notification_settings)

# Shared by the regular calendar-tick path above and the daemon's early wake-up for a
# due snooze (homeaudio/vcal/notifications/daemon.py's check_for_due_snooze), so a snoozed
# notification goes through the exact same text/audio pipeline either way.
def build_and_play_notifications(event_notifications: list[EventNotification], base_time, scene: SceneProtocol, event_notification_settings: EventNotificationSettings = EventNotificationSettings()):
    if event_notifications:
        LastPlayedState().save(event_notifications, base_time)

        # Separate alarm and announcement notifications
        announcement_event_notifications = [event for event in event_notifications if event.type == NotificationType.ANNOUNCE]
        alarm_event_notifications = [event for event in event_notifications if event.type == NotificationType.ALARM]

        announcement_texts = NotificationTextBuilder(announcement_event_notifications, base_time).build()
        alarm_texts = NotificationTextBuilder(alarm_event_notifications, base_time).build()

        announcements_file = (
            AnnouncementAudio(announcement_texts, base_time, SoundEffectSelector(event_notification_settings.announcements.sound_effect_probability)).build_announcement_file()
            if announcement_event_notifications else None
        )
        alarm_audio_file = AlarmAudio(alarm_texts, event_notification_settings.alarms, base_time).build_alarm_file() if alarm_event_notifications else None

        play_notifications(announcements_file, alarm_audio_file, scene)

def get_event_notifications(base_time, window, calendar_data: list[CalendarDay], event_notification_settings: EventNotificationSettings):
    notification_rules = event_notification_settings.enabled_notification_rules()
    alarm_finder = NotificationFinder(calendar_data, base_time, window, notification_rules)
    event_notifications = alarm_finder.find_notification_events()
    return event_notifications

def get_all_event_notifications(event_notification_settings: EventNotificationSettings = EventNotificationSettings(), calendar_source: CalendarSource = CalendarSource(DATA_FILE)):
    calendar_days = calendar_source.load_data_from_file()

    notification_rules = event_notification_settings.enabled_notification_rules()
    notifications = []
    for day in calendar_days:
        for event in day.timed_events:
            notifications.extend(event.notifications(notification_rules))

    return notifications

def get_all_events(calendar_source: CalendarSource = CalendarSource(DATA_FILE)):
    calendar_days = calendar_source.load_data_from_file()
    events_by_day = [
        (calendar_day.date, event.start_time is not None, event.start_time, event)
        for calendar_day in calendar_days
        for event in calendar_day.all_events()
    ]
    events_by_day.sort(key=lambda item: (item[0], item[1], item[2] or datetime.min))
    return [event for *_, event in events_by_day]

def get_calendar_refreshed_at(calendar_source: CalendarSource = CalendarSource(DATA_FILE)) -> datetime | None:
    calendar_source.load_data_from_file()
    return calendar_source.refreshed_at

