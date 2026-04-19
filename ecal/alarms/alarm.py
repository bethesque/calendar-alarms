import logging
from datetime import datetime, timedelta

from ecal.alarms.sound import build_alarm_audio
from ecal.alarms.text_to_voice import text_to_voice_file
from ecal.alarms.mpv import MpvProcess, fade_up
from ecal.alarms import ALARM_FILE, ALARM_SOCKET, ANNOUNCEMENT_SOCKET, MIXED_SOCKET, SILENCE_FILE, DEFAULT_VOLUME
from ecal.env import SINGLE_STREAM, DATA_DIRECTORY


logger = logging.getLogger(__name__)

def play_alarm(announcement_files):
    if SINGLE_STREAM:
        play_alarm_with_single_stream(announcement_files)
    else:
        play_alarm_with_dual_streams(announcement_files)

def play_alarm_with_single_stream(announcement_files):
    audio_file = DATA_DIRECTORY + "/alarm_mix.wav"
    # TODO use all announcement files
    build_alarm_audio(
        announcement_file=announcement_files[0],
        alarm_file=ALARM_FILE,
        output_file=audio_file,
        duration=300
    )

    # Play the mixed audio file
    alarm_player = MpvProcess(MIXED_SOCKET)
    alarm_player.start()

    if not alarm_player.wait_for_ipc(timeout=30.0):
        logger.error(f"Error: mpv IPC socket at {MIXED_SOCKET} not ready")
        exit(1)

    alarm_player.set_volume(0)
    alarm_player.play_file(audio_file)
    fade_up([(alarm_player, 60)], 10, 10)
    fade_up([(alarm_player, 90)], 45, 10)

def play_alarm_with_dual_streams(announcement_files):
    alarm_player, announcement_player = prepare_mvp_processes()

    # Play the alarm track
    alarm_player.play_file_on_loop(ALARM_FILE, 240)

    # Start the looping announcement playlist
    announcement_player.play_files_on_loop([SILENCE_FILE] + announcement_files, 240)

    # Fade up to max volume over 45 seconds
    fade_up([(alarm_player, 90), (announcement_player, 100)], 45, 10)

def prepare_mvp_processes():
    # Make sure the mpv processes are started and ready
    alarm_player = MpvProcess(ALARM_SOCKET)
    announcement_player = MpvProcess(ANNOUNCEMENT_SOCKET)

    alarm_player.start()
    announcement_player.start()

    if not alarm_player.wait_for_ipc(timeout=30.0):
        logger.error(f"Error: mpv alarm IPC socket at {ALARM_SOCKET} not ready")
        exit(1)

    if not announcement_player.wait_for_ipc(timeout=30.0):
        logger.error(f"Error: mpv announcement IPC socket at {ANNOUNCEMENT_SOCKET} not ready")
        exit(1)

    # Set the initial volume
    alarm_player.set_volume(DEFAULT_VOLUME)
    announcement_player.set_volume(DEFAULT_VOLUME)

    return (alarm_player, announcement_player)


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