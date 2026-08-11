import logging
import argparse
from vcal.env import LOG_LEVEL
from vcal.log_config import setup_logging_for_announcements
from vcal.scene import Scene
from vcal.housie_talkie.speak import play_announcement as play_announcement_func, TextAnnouncementRequest

setup_logging_for_announcements(str(LOG_LEVEL))

logger = logging.getLogger(__name__)

def play_announcement():
    parser = argparse.ArgumentParser(description="Play a one-off announcement")
    parser.add_argument(
        "--message",
        required=True,
        help="The message to announce"
    )

    parser.add_argument(
        "--sound_effect_file_name",
        help="The name of the sound effect file to play"
    )
    args = parser.parse_args()

    try:
        logger.info(f"Playing announcement: {args.message}")
        play_announcement_func(TextAnnouncementRequest(message=args.message, sound_effect=args.sound_effect_file_name,  scene= Scene()))
    except Exception:
        logger.exception("Error playing announcements")
        exit(1)
