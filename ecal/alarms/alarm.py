import logging
import glob
from datetime import datetime, timedelta
from ecal.alarms.sound import build_alarm_audio, join_mp3s_to_wav
from ecal.alarms.text_to_voice import text_to_voice_file
from ecal.alarms.mpd import fade_up, fade_out, mpd_connection
from ecal.select_item import select_item_by_date
from ecal.alarms import ALARMS_DIRECTORY
from ecal.env import OUTPUT_AUDIO_DIRECTORY, INITIAL_VOLUME

logger = logging.getLogger(__name__)

"""
Takes a list of CalenderDays and finds any alarms due within the given time window.
"""
class AlarmFinder:
    def __init__(self, calendar_days, base_time, window):
        self.calendar_days = calendar_days
        self.base_time = base_time
        self.window = window

    def find_alarm_events(self):
        start, end = self._get_time_window(self.base_time, self.window)
        logging.info(
            "Time window: %s → %s (WINDOW=%d mins)",
            start.isoformat(),
            end.isoformat(),
            self.window)
        return self._find_alarm_events_in_range(start, end)

    def _get_time_window(self, base_time, window_minutes):
        # Round down to nearest multiple of WINDOW
        minute = (self.base_time.minute // window_minutes) * window_minutes
        start_time = self.base_time.replace(minute=minute, second=0, microsecond=0)
        end_time = start_time + timedelta(minutes=window_minutes)
        return start_time, end_time

    def _find_alarm_events_in_range(self, start_time, end_time):
        matching_events = []

        for day in self.calendar_days:
            for event in day.timed_events:
                if event.alarm_time_within_window(start_time, end_time):
                    matching_events.append(event)

        return matching_events

    def _log_results(self, results):
        for result in results:
            logging.info(
                "Matched event: %s | %s",
                result.start_time,
                result.summary
            )
        logging.info("Total matched events: %d", len(results))

"""
Builds the alarm audio by using TTS to read out the event descriptions, and
mixing in background alarm music.
"""
class AlarmAudio:
    def __init__(self, events, base_time):
        self.events = events
        self.base_time = base_time

    def build_alarm_file(self):
        joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/announcement.wav"
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
        return self._deduplicate_list([text_to_voice_file(self._announcement_for_event(event)) for event in self.events])

    def _announcement_for_event(self, event):
        summary = event.summary if event.summary else "an event"
        if event.alarm_offset() > 0:
            return f"It will be time for {summary} in {event.alarm_offset()} minutes"
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


def play_alarm(audio_file, before_alarm_hook=None):
    if before_alarm_hook:
        before_alarm_hook()
    with mpd_connection() as alarm_player:
        logger.info(f"Playing alarm {audio_file}")
        alarm_player.set_volume(INITIAL_VOLUME)
        alarm_player.play_file(audio_file)
        fade_up([(alarm_player, 100)], 45, 10)
    # after alarm hook if nobody stops it?

def stop_alarm(after_alarm_hook=None):
    # Stop alarm
    logger.info("Stopping alarm...")
    message = ""
    try:
        with mpd_connection() as alarm_player:
            if alarm_player.is_running():
                fade_out([alarm_player], 3)
                alarm_player.stop()
                message = "Alarm stopped."
            else:
                message = "MPD is not running. No alarm to stop."
    except Exception as e:
        logger.error(f"Error stopping alarm: {e}")

    logger.info(message)

    after_alarm_hook() if after_alarm_hook else None

def check_for_alarms(base_time, window, calendar_data, before_alarm_hook=None):
    events = AlarmFinder(calendar_data, base_time, window).find_alarm_events()

    if events:
        alarm_audio_file = AlarmAudio(events, base_time).build_alarm_file()
        play_alarm(alarm_audio_file, before_alarm_hook)

