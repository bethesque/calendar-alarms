import logging
import json
import logging
import os
import argparse
from datetime import datetime
from ecal.alarms.alarm import play_alarm
from ecal.env import LOG_LEVEL
from ecal.alarms.mpd import fade_out, fade_up, mpd_connection
from ecal.log_config import setup_logging_for_alarms
from ecal.calendar.google_calendar import CalendarSource

from ecal.env import DATA_DIRECTORY, PLAYERS, CACHE_DIRECTORY
from ecal.alarms.alarm import check_for_alarms
from ecal.music_assistant import MusicAssistant, MusicAssistantState



setup_logging_for_alarms(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

def load_events(file_path):
    return CalendarSource(cache_file_path=file_path).load_data_from_file()

def check_alarms():
    parser = argparse.ArgumentParser(description="Check for alarms in calendar events")
    parser.add_argument(
        "--base_time",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="Base time for checking alarms (ISO format, defaults to current time)"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=5,
        help="Time window in minutes for checking alarms (default: 5)"
    )

    parser.add_argument(
        "--calendar_file",
        default=os.path.join(DATA_DIRECTORY, "calendar.json"),
        help=f"Path to the calendar JSON file (default: {os.path.join(DATA_DIRECTORY, 'calendar.json')})"
    )

    parser.add_argument('--handle-music-assistant', action='store_true', help="Fade out music assistant before playing alarms")

    args = parser.parse_args()

    logger.info(f"Checking for alarms in {args.calendar_file}...")

    base_time = args.base_time or datetime.now().astimezone()
    calendar_data = load_events(args.calendar_file)

    def pause_music_assistant_players():
        logger.info("Pausing Music Assistant players (if any)...")
        ma = MusicAssistant.build_for_players_with_names(PLAYERS)
        ma.fetch_current_state()
        MusicAssistantState.save(ma, CACHE_DIRECTORY + "/music_assistant_state.json")
        ma.fade_out_and_pause()

    before_alarm_hook = pause_music_assistant_players if args.handle_music_assistant else None

    check_for_alarms(base_time, args.window, calendar_data, before_alarm_hook)

def test_alarm():
    try:
        print("Testing alarm... press Ctrl+C to stop")
        play_alarm(["audio/test_announcement.mp3"])
    except KeyboardInterrupt as e:
        logger.info("Stopping test alarm...")
        with mpd_connection() as alarm_player:
            fade_out([alarm_player], 3)
        exit(0)

def stop_alarm():
    try:
        with mpd_connection() as alarm_player:
            fade_out([alarm_player], 3)
            logger.info("Alarm stopped.")
    except Exception as e:
        logger.error(f"Error stopping alarm: {e}")
        exit(1)

def play_test_file():
    # get audio file path from the command line argument
    parser = argparse.ArgumentParser(description="Play a test audio file")
    parser.add_argument(
        "audio_file",
        help="Path to the audio file to play"
    )
    args = parser.parse_args()
    audio_file = args.audio_file

    try:
        # Play the mixed audio file
        with mpd_connection() as alarm_player:
            alarm_player.set_volume(60)
            alarm_player.play_file(audio_file)
            fade_up([(alarm_player, 80)], 5, 10)
    except Exception as e:
        logger.error(f"Error playing alarm: {e}")
        exit(1)
