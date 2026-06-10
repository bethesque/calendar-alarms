import os
import logging
from gtts import gTTS
from vcal.string_utils import sanitise_filename
from vcal.random_text import TextFileOptionsSource, select_text
from vcal.env import CACHE_DIRECTORY, GOOGLE_TRANSLATE_LANG, DEFAULT_GOOGLE_TRANSLATE_TLD

DEFAULT_ANNOUCEMENT_FILE = "audio/default_announcement.mp3"
AUDIO_CACHE_DIR = os.path.join(CACHE_DIRECTORY, "audio")

logger = logging.getLogger(__name__)

"""
Converts text to a voice file and saves it to the cache directory.
Returns the path to the saved audio file.
"""
def text_to_voice_file(text, word_limit=1000, audio_cache_directory=AUDIO_CACHE_DIR):
    logger.info(f"Converting text to voice: {text}")
    if word_limit is not None:
        words = text.split()
        text_to_say = " ".join(words[:word_limit])
    else:
        text_to_say = text
    tld = gtts_tld()
    logger.debug(f"Using tld '{tld}' for gTTS")
    audio_file_path = get_file_path_for_text(text_to_say, tld, audio_cache_directory)
    # if the file already exists, return it
    if os.path.exists(audio_file_path):
        logger.debug("Audio file already exists for text: %s, returning existing file: %s", text_to_say, audio_file_path)
        return audio_file_path

    try:
        logger.debug("Generating TTS for text: %s, saving to: %s", text_to_say, audio_file_path)
        tts = gTTS(text_to_say, timeout=5, lang=GOOGLE_TRANSLATE_LANG, tld=tld)

        # Ensure the cache directory exists
        os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
        tts.save(audio_file_path)
    except Exception as e:
        logger.error(f"Error generating TTS for text: {text_to_say}. Error: {e}")
        return DEFAULT_ANNOUCEMENT_FILE

    return audio_file_path

def text_to_voice_file_daily_summary(text, cache_directory=AUDIO_CACHE_DIR):
    audio_file_path = get_file_path_for_text("daily_summary", gtts_tld(), cache_directory)

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

def get_file_path_for_text(text, tld, cache_directory=AUDIO_CACHE_DIR):
    audio_file_path = os.path.join(cache_directory, sanitise_filename(text + "_" + tld) + ".mp3")
    return audio_file_path

def gtts_tld():
    # Randomly select a tld to keep things interesting.
    tld = select_text(DEFAULT_GOOGLE_TRANSLATE_TLD, 1/5, TextFileOptionsSource(file_name="accent_tld_choices.txt"))
    return tld if tld else DEFAULT_GOOGLE_TRANSLATE_TLD

if __name__ == "__main__":
    test_text = "This is a test event. Don't do anything."
    audio_file = text_to_voice_file(test_text)
    print(f"Generated audio file: {audio_file}")