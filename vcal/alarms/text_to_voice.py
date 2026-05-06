import os
import logging
from gtts import gTTS
from ecal.string_utils import sanitise_filename
from ecal.random_text import select_text
from ecal.env import CACHE_DIRECTORY, GOOGLE_TRANSLATE_LANG, DEFAULT_GOOGLE_TRANSLATE_TLD

DEFAULT_ANNOUCEMENT_FILE = "audio/default_announcement.mp3"
AUDIO_CACHE_DIR = os.path.join(CACHE_DIRECTORY, "audio")

logger = logging.getLogger(__name__)

"""
Converts text to a voice file and saves it to the cache directory.
Returns the path to the saved audio file.
"""
def text_to_voice_file(text, audio_cache_directory=AUDIO_CACHE_DIR):
    logger.info(f"Converting text to voice: {text}")
    # Take first 20 words to avoid long processing times and large audio files
    words = text.split()
    truncated_text = " ".join(words[:20])
    tld = gtts_tld()
    logger.debug(f"Using tld '{tld}' for gTTS")
    audio_file_path = os.path.join(audio_cache_directory, sanitise_filename(truncated_text + "_" + tld) + ".mp3")
    # if the file already exists, return it
    if os.path.exists(audio_file_path):
        logger.debug("Audio file already exists for text: %s, returning existing file: %s", truncated_text, audio_file_path)
        return audio_file_path

    try:
        logger.debug("Generating TTS for text: %s, saving to: %s", truncated_text, audio_file_path)
        tts = gTTS(truncated_text, timeout=5, lang=GOOGLE_TRANSLATE_LANG, tld=tld)

        # Ensure the cache directory exists
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        tts.save(audio_file_path)
    except Exception as e:
        logger.error(f"Error generating TTS for text: {truncated_text}. Error: {e}")
        return DEFAULT_ANNOUCEMENT_FILE

    return audio_file_path

def text_to_voice_file_daily_summary(text, cache_directory=AUDIO_CACHE_DIR):
    audio_file_path = os.path.join(cache_directory, "daily_summary.mp3")

    try:
        logger.debug("Generating TTS for text: %s, saving to: %s", text, audio_file_path)
        tld = gtts_tld()
        tts = gTTS(text, timeout=5, lang=GOOGLE_TRANSLATE_LANG, tld=tld)

        # Ensure the cache directory exists
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        tts.save(audio_file_path)
    except Exception as e:
        logger.error(f"Error generating TTS for text: {text}. Error: {e}")
        # TODO new announcement file for errors
        return DEFAULT_ANNOUCEMENT_FILE

    return audio_file_path

def gtts_tld():
    # Randomly select a tld to keep things interesting.
    tld = select_text(DEFAULT_GOOGLE_TRANSLATE_TLD, 1/5, "accent_tld_choices.txt")
    return tld if tld else DEFAULT_GOOGLE_TRANSLATE_TLD

if __name__ == "__main__":
    test_text = "This is a test event. Don't do anything."
    audio_file = text_to_voice_file(test_text)
    print(f"Generated audio file: {audio_file}")