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

def play_alarm(announcement_files, before_alarm_hook=None):
    joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/announcement.wav"
    join_mp3s_to_wav(announcement_files, joined_announcement_file)

    audio_file = OUTPUT_AUDIO_DIRECTORY + "/alarm_mixed.wav"

    alarm_file = get_alarm_file()

    build_alarm_audio(
        announcement_file=joined_announcement_file,
        alarm_file=alarm_file,
        output_file=audio_file,
        duration=300
    )


    # Play the mixed audio file
    with mpd_connection() as alarm_player:
        if before_alarm_hook:
            before_alarm_hook()
        logger.info(f"Playing alarm {audio_file}")
        alarm_player.set_volume(INITIAL_VOLUME)
        alarm_player.play_file(audio_file)
        fade_up([(alarm_player, 100)], 45, 10)

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

def parse_iso(dt_str):
    return datetime.fromisoformat(dt_str)

def deduplicate_list(items):
    return list(dict.fromkeys(items))

def get_time_window(base_time, window_minutes):
    # Round down to nearest multiple of WINDOW
    minute = (base_time.minute // window_minutes) * window_minutes
    start_time = base_time.replace(minute=minute, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=window_minutes)
    return start_time, end_time

def find_alarm_events_in_range(calendar_days, start_time, end_time):
    matching_events = []

    for day in calendar_days:
        for event in day.timed_events:
            if event.alarm_time_within_window(start_time, end_time):
                matching_events.append(event)

    return matching_events

def log_results(results):
    for result in results:
        logging.info(
            "Matched event: %s | %s",
            result.start_time,
            result.summary
        )
    logging.info("Total matched events: %d", len(results))

def check_for_alarms(base_time, window, calendar_data, before_alarm_hook=None):
    start, end = get_time_window(base_time, window)

    logging.info(
        "Time window: %s → %s (WINDOW=%d mins)",
        start.isoformat(),
        end.isoformat(),
        window
    )
    results = find_alarm_events_in_range(calendar_data, start, end)
    log_results(results)

    if results:
        play_alarm(announcement_files_for_events(results), before_alarm_hook)

def announcement_files_for_events(events):
    return deduplicate_list([text_to_voice_file(announcement_for_event(event)) for event in events])

def announcement_for_event(event):
    summary = event.summary if event.summary else "an event"
    if event.alarm_offset() > 0:
        return f"It will be time for {summary} in {event.alarm_offset()} minutes"
    else:
        return f"It's time for {summary}"

def get_alarm_file(date=None):
    alarm_files = get_alarm_files()
    if date is None:
        date = datetime.now().date()
    # New alarm every 14 days
    return select_item_by_date(sorted(alarm_files), date, 14)

def get_alarm_files():
    # Get all mp3 files in the ALARMS_DIRECTORY
    alarm_files = glob.glob(f"{ALARMS_DIRECTORY}/*.mp3")
    if not alarm_files:
        raise FileNotFoundError(f"No alarm files found in {ALARMS_DIRECTORY}")
    return alarm_files
