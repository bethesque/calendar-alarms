import logging
from datetime import datetime, timedelta

from ecal.alarms.mpd import MpdProcess
from ecal.alarms.sound import build_alarm_audio
from ecal.alarms.text_to_voice import text_to_voice_file
from ecal.alarms.mpd import MpdProcess, fade_up
from ecal.alarms import ALARM_FILE, DEFAULT_VOLUME
from ecal.env import MPD_HOST, MPD_PORT, OUTPUT_AUDIO_DIRECTORY


logger = logging.getLogger(__name__)

def play_alarm(announcement_files):
    audio_file = OUTPUT_AUDIO_DIRECTORY + "/alarm_mixed.wav"
    # TODO use all announcement files
    build_alarm_audio(
        announcement_file=announcement_files[0],
        alarm_file=ALARM_FILE,
        output_file=audio_file,
        duration=300
    )

    logger.info(f"Playing alarm {audio_file}")

    # Play the mixed audio file
    alarm_player = MpdProcess(MPD_HOST, MPD_PORT)

    alarm_player.set_volume(DEFAULT_VOLUME)
    alarm_player.play_file(audio_file)
    logger.info("Alarm started, fading up volume...")
    fade_up([(alarm_player, 100)], 45, 10)

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

def find_alarm_events_in_range(events_data, start_time, end_time):
    matching_events = []

    for day in events_data:
        for event in day.get("timed_events", []):
            start_str = event.get("start_time")
            description = event.get("description")

            # Discard events without a start time or without the #alarm tag in the description
            if not start_str or (not description or "#alarm" not in description):
                continue

            event_start = parse_iso(start_str)

            if start_time <= event_start < end_time:
                matching_events.append(event)

    return matching_events

def log_results(results):
    for result in results:
        logging.info(
            "Matched event: %s | %s",
            result.get("start_time"),
            result.get("summary")
        )
    logging.info("Total matched events: %d", len(results))

def check_for_alarms(base_time, window, calendar_data):
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
        play_alarm(announcement_files_for_events(results))

def announcement_files_for_events(events):
    return deduplicate_list([text_to_voice_file(announcement_for_event(event)) for event in events])

def announcement_for_event(event):
    summary = event.get("summary", "an event")
    return f"It's time for {summary}"