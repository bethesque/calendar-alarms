import logging
import glob
from pathlib import Path
import random
import re
import time
from datetime import datetime, timedelta
from homeaudio.vcal.cal.google_calendar import EventNotification, NotificationType, CalendarSource
from homeaudio.audio.sound import build_alarm_audio, join_mp3s_to_wav, build_aggressive_alarm_audio, join_mixed_files_to_wav
from homeaudio.vcal.notifications.text_to_voice import text_to_voice_file
from homeaudio.audio.mpd import fade_out, fade_up, mpd_connection
from homeaudio.audio.select_item import select_item_by_date
from homeaudio.vcal.notifications import GENTLE_ALARMS_DIRECTORY, AGGRESSIVE_ALARMS_DIRECTORY, PRE_ANNOUNCEMENT_BELL, OUTPUT_AUDIO_DIRECTORY, SILENCE_HALF_SEC
from homeaudio.audio.sound import track_length
from homeaudio.audio.scene import SceneProtocol, HomeAssistantScene
from homeaudio.audio.settings import AlarmSettings, SnapcastSettings, MpdSettings, EventNotificationSettings
from homeaudio.audio.snapcast import SnapserverManager
from homeaudio.audio.snapserver import Snapserver
from homeaudio.housie_talkie.models import SoundEffectSelector

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

class VerbIdentifier:
    def __init__(self, verb_file: str):
        with open(verb_file, encoding="utf-8") as f:
            self.verbs = set({line.strip() for line in f if line.strip()})

    def is_verb(self, word: str):
        return word.lower() in self.verbs

class NotificationTextBuilder:
    def __init__(self, event_notifications: list[EventNotification], base_time):
        self.event_notifications = event_notifications
        self.base_time = base_time
        self.verb_identifier = VerbIdentifier(str(Path(__file__).resolve().parent.joinpath("verbs.txt")))

    def build(self) -> list[str]:
        return self._deduplicate_list([self._announcement_for_event(event) for event in self.event_notifications])

    def _announcement_for_event(self, event_notification: EventNotification):
        announcement: str

        if event_notification.notification_rule and event_notification.notification_rule.replace and event_notification.notification_rule.reminder:
            announcement = event_notification.notification_rule.reminder
        else:
            summary = event_notification.event.summary if event_notification.event.summary else "an event"
            if event_notification.offset > 0:
                announcement = f"It will be time {self.to_or_for(summary)} {summary} in {event_notification.offset} minutes"
            else:
                announcement = f"It's time {self.to_or_for(summary)} {summary}"

            if event_notification.notification_rule and event_notification.notification_rule.reminder:
                announcement = announcement + ". " + event_notification.notification_rule.reminder

        return announcement

    def to_or_for(self, event_summary):
        first_word = re.sub(r"[^\w]", "", event_summary.split()[0]).lower()
        return "to" if self.verb_identifier.is_verb(first_word) else "for"


    def _deduplicate_list(self, items):
        return list(dict.fromkeys(items))

"""
Builds the alarm audio by using TTS to read out the event descriptions, and
mixing in background alarm music.
"""
class AlarmAudio:
    def __init__(self, notification_texts: list[str], alarm_settings: AlarmSettings, base_time):
        self.notification_texts = notification_texts
        self.base_time = base_time
        self.alarm_settings = alarm_settings


    def build_alarm_file(self):
        joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/alarm.wav"
        join_mp3s_to_wav(self._announcement_files_for_events(), joined_announcement_file)

        gentle_audio_file = OUTPUT_AUDIO_DIRECTORY + "/alarm_mixed.wav"

        alarm_file = self._get_alarm_file()

        build_alarm_audio(
            announcement_file=joined_announcement_file,
            alarm_file=alarm_file,
            output_file=gentle_audio_file,
            duration=self.alarm_settings.gentle_alarm_duration
        )

        files_to_loop = [gentle_audio_file]

        if self.alarm_settings.aggressive_alarm_loops > 0:
            loud_noise_warning_file = text_to_voice_file("Warning - an aggressively loud noise is about to be played to get your attention.")

            aggressive_audio_file = OUTPUT_AUDIO_DIRECTORY + "/alarm_aggressive.wav"

            build_aggressive_alarm_audio(
                announcement_file=joined_announcement_file,
                alarm_file=self.get_aggressive_alarm_file(),
                output_file=aggressive_audio_file,
                loops=self.alarm_settings.aggressive_alarm_loops
            )

            files_to_loop.append(loud_noise_warning_file)
            files_to_loop.append(SILENCE_HALF_SEC)
            files_to_loop.append(aggressive_audio_file)

        all_files = files_to_loop * self.alarm_settings.full_loops
        alarm_file = OUTPUT_AUDIO_DIRECTORY + "/alarm.wav"

        join_mixed_files_to_wav(all_files, alarm_file)

        return alarm_file

    def _announcement_files_for_events(self):
        return [text_to_voice_file(text) for text in self.notification_texts]

    def _get_alarm_file(self):
        alarm_files = self._get_alarm_background_files()
        # New alarm every 14 days
        return select_item_by_date(sorted(alarm_files), self.base_time.date(), 14)

    def get_aggressive_alarm_file(self):
        return random.choice(self._get_aggressive_alarm_files())

    def _get_alarm_background_files(self):
        # Get all mp3 files in the ALARMS_DIRECTORY
        alarm_files = glob.glob(f"{GENTLE_ALARMS_DIRECTORY}/*.mp3")
        if not alarm_files:
            raise FileNotFoundError(f"No alarm files found in {GENTLE_ALARMS_DIRECTORY}")
        return alarm_files

    def _get_aggressive_alarm_files(self):
        alarm_files = [
            f for ext in ("*.wav", "*.mp3")
            for f in glob.glob(f"{AGGRESSIVE_ALARMS_DIRECTORY}/{ext}")
        ]
        if not alarm_files:
            raise FileNotFoundError(f"No alarm files found in {AGGRESSIVE_ALARMS_DIRECTORY}")
        return alarm_files


"""
Builds the alarm audio by using TTS to read out the event descriptions, and
mixing in background alarm music.
"""
class AnnouncementAudio:
    def __init__(self, notification_texts: list[str], base_time, sound_effect_selector: SoundEffectSelector):
        self.notification_texts = notification_texts
        self.base_time = base_time
        self.sound_effect_selector = sound_effect_selector

    def build_announcement_file(self):
        joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/announcement.wav"
        files = self.preannouncement_files() + self._announcement_files_for_events()
        join_mp3s_to_wav(files, joined_announcement_file)

        return joined_announcement_file

    def _announcement_files_for_events(self):
        return [text_to_voice_file(text) for text in self.notification_texts]

    def preannouncement_files(self) -> list[str]:
        file = self.sound_effect_selector.get_random_sound_effect_file()
        if file:
            return [PRE_ANNOUNCEMENT_BELL, file]
        else:
            return [PRE_ANNOUNCEMENT_BELL]

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
    with mpd_connection(mpd_settings) as alarm_player:
        logger.info(f"Playing announcements {announcements_file}")
        alarm_player.set_volume(mpd_settings.volumes.tts)
        alarm_player.play_file(announcements_file)
    time.sleep(track_length(announcements_file))

def _play_event_alarm(alarms_file, mpd_settings: MpdSettings):
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
                alarm_player.set_volume(0)
                #fade_out([alarm_player], 1, 5)
                alarm_player.stop()
                message = "Alarm stopped."
            else:
                message = "MPD is not running. No alarm to stop."
    except Exception as e:
        logger.error(f"Error stopping alarm: {e}")

    logger.info(message)

    after_alarm_hook() if after_alarm_hook else None

def mute_alarm_for_area_of_player(player, snapcast_settings: SnapcastSettings = SnapcastSettings()):
    area = snapcast_settings.snapclient_settings(player).area
    if area:
        names = [ snapclient.name for snapclient in snapcast_settings.snapclients_for_area(area)]
        snapserver = Snapserver(snapcast_settings.snapserver_rpc_url)
        snapserver.mute_clients(names)
    else:
        logger.info(f"No area found for player {player}, cannot mute area")

def test_alarm():
    date_string = "2026-04-06T00:00:00+10:00"
    base_time = datetime.fromisoformat("2026-04-06T00:00:00+10:00")

    days = [
        {
            "date":  base_time.strftime("%Y-%m-%d"),
            "date_time": date_string,
            "timed_events": [
                {
                    "description": "#alarm",
                    "end_time": None,
                    "owner": "Beth",
                    "recurring": False,
                    "start_time": date_string,
                    "summary": "test the alarm"
                },
            ],
            "whole_day_events": []
        }
    ]

    calendar_data = CalendarSource(cache_file_path="").load_data_from_any(days)

    check_for_notifications(base_time, 5, calendar_data, HomeAssistantScene())


def check_for_notifications(base_time, window, calendar_data, scene:SceneProtocol, event_notification_settings: EventNotificationSettings = EventNotificationSettings()):
    notification_rules = event_notification_settings.notification_rules
    alarm_finder = NotificationFinder(calendar_data, base_time, window, notification_rules)
    event_notifications = alarm_finder.find_notification_events()

    if event_notifications:
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

