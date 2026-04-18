from ecal.string_utils import sanitise_filename
from gtts import gTTS
import os
import logging

DEFAULT_ANNOUCEMENT_FILE = "audio/default_announcement.mp3"

logger = logging.getLogger(__name__)

from ecal.env import CACHE_DIRECTORY

"""
Converts text to a voice file and saves it to the cache directory.
Returns the path to the saved audio file.
"""
def text_to_voice_file(text, cache_directory=CACHE_DIRECTORY):
    # Take first 20 words to avoid long processing times and large audio files
    words = text.split()
    truncated_text = " ".join(words[:20])
    audio_file_path = os.path.join(cache_directory, "audio", sanitise_filename(truncated_text) + ".mp3")
    # if the file already exists, return it
    if os.path.exists(audio_file_path):
        logger.debug("Audio file already exists for text: %s, returning existing file: %s", truncated_text, audio_file_path)
        return audio_file_path

    try:
        logger.debug("Generating TTS for text: %s, saving to: %s", truncated_text, audio_file_path)
        tts = gTTS(truncated_text, timeout=5)

        # Ensure the cache directory exists
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        tts.save(audio_file_path)
    except Exception as e:
        logger.error(f"Error generating TTS for text: {truncated_text}. Error: {e}")
        return DEFAULT_ANNOUCEMENT_FILE

    return audio_file_path

def text_to_voice_file_daily_summary(text, cache_directory=CACHE_DIRECTORY):
    # Take first 20 words to avoid long processing times and large audio files

    audio_file_path = os.path.join(cache_directory, "audio", "daily_summary.mp3")

    try:
        logger.debug("Generating TTS for text: %s, saving to: %s", text, audio_file_path)
        tts = gTTS(text, timeout=5)

        # Ensure the cache directory exists
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        tts.save(audio_file_path)
    except Exception as e:
        logger.error(f"Error generating TTS for text: {text}. Error: {e}")
        # TODO new announcement file for errors
        return DEFAULT_ANNOUCEMENT_FILE

    return audio_file_path

if __name__ == "__main__":
    test_text = "This is a test event. Don't do anything."
    audio_file = text_to_voice_file(test_text)
    print(f"Generated audio file: {audio_file}")