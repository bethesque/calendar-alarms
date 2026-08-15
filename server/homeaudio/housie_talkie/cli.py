import logging
import argparse
from homeaudio.env import LOG_LEVEL
from homeaudio.audio.log_config import setup_logging_for_announcements
from homeaudio.audio.scene import Scene
from homeaudio.housie_talkie.core import play_tts_announcement as play_announcement_func, TtsAnnouncementRequest

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
        play_announcement_func(TtsAnnouncementRequest(message=args.message, sound_effect=args.sound_effect_file_name,  scene= Scene()))
    except Exception:
        logger.exception("Error playing announcements")
        exit(1)
