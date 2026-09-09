
import logging
from datetime import datetime, timedelta
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarSource
from homeaudio.audio.sound import join_mp3s_to_wav
from homeaudio.vcal.event_notifications.text_to_voice import text_to_voice_file
from homeaudio.audio.mpd import mpd_connection
from homeaudio.vcal.event_notifications import OUTPUT_AUDIO_DIRECTORY, POST_ANNOUNCEMENT_SILENCE
from homeaudio.audio.scene import scene_for_env
from homeaudio.audio.settings import MorningAnnouncementsSettings, SchoolAnnouncementsSettings, SnapcastSettings, MpdSettings, EventNotificationSettings

from homeaudio.audio.snapserver import Snapserver
from homeaudio.vcal.event_notifications.snooze import LastPlayedState, SnoozeState
from homeaudio.env import CALENDAR_DATA_DIRECTORY
from homeaudio.vcal.school_announcements.core import check_for_announcement as check_for_school_announcements
from homeaudio.vcal.morning_announcements.core import check_for_announcement as check_for_morning_announcements
from homeaudio.vcal.event_notifications.core import check_for_event_notifications as check_for_event_notifications
from homeaudio.vcal.playback import NotificationFiles, play_notifications, play_file

logger = logging.getLogger(__name__)

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
        play_file(_build_one_off_announcement_file("Nothing to snooze"))
        return

    event_notifications = last_played.load()
    base_time = last_played.load_base_time()

    if not event_notifications or not base_time:
        play_file(_build_one_off_announcement_file("Nothing to snooze"))
        return

    snooze_minutes = EventNotificationSettings().snooze_minutes
    replay_at = base_time + timedelta(minutes=snooze_minutes)
    actual_snooze_minutes = int((replay_at - datetime.now().astimezone()).total_seconds() // 60)
    SnoozeState().save(event_notifications, replay_at)
    logger.info(f"Snoozed last alarm for {actual_snooze_minutes} minutes until {replay_at}")
    play_file(_build_one_off_announcement_file(f"Snoozing for {actual_snooze_minutes} minutes"))

    if after_alarm_hook:
        after_alarm_hook()

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
                    "description": "#announce",
                    "end_time": None,
                    "owner": "Beth",
                    "calendar_id": "id",
                    "recurring": False,
                    "start_time": now.isoformat(),
                    "summary": "do an announcement"
                },
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

    announcements_file, alarm_audio_file = check_for_event_notifications(now, 5, calendar_data, EventNotificationSettings())
    notification_files = NotificationFiles(event_alarms_file=alarm_audio_file, event_announcements_file=announcements_file)
    play_notifications(notification_files, scene_for_env())

# Gathers what's due at base_time (calendar-driven notifications plus any due snoozes) and builds
# their announcement/alarm audio files, without playing them. Used by the daemon's early wake-up
# (homeaudio/vcal/notifications/daemon.py) so it can build audio ahead of a scheduled tick and play
# right on time; check_for_notifications above uses it too, just followed immediately by playing.
def prepare_notification_files(base_time, window, calendar_days: list[CalendarDay], event_notification_settings: EventNotificationSettings = EventNotificationSettings()) -> NotificationFiles | None:

    announcements_file, alarm_audio_file = check_for_event_notifications(base_time, window, calendar_days, event_notification_settings)

    scheduled_announcements_files = []
    if file := check_for_morning_announcements(base_time, window, calendar_days, MorningAnnouncementsSettings()):
        scheduled_announcements_files.append(file)
    if file := check_for_school_announcements(base_time, window, calendar_days, SchoolAnnouncementsSettings()):
        scheduled_announcements_files.append(file)

    if alarm_audio_file or announcements_file or scheduled_announcements_files:
        return NotificationFiles(event_alarms_file=alarm_audio_file, event_announcements_file=announcements_file, scheduled_announcements_files=scheduled_announcements_files)
    else:
        return None
