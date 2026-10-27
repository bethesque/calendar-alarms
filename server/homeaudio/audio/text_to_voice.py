import hashlib
import os
import logging
import time
from gtts import gTTS, gTTSError
from homeaudio.env import GOOGLE_TRANSLATE_LANG, DEFAULT_GOOGLE_TRANSLATE_TLD
from homeaudio.audio.random_text import select_option_pseudorandomly, ListOptionsSource
from homeaudio.audio.settings import GoogleTextToSpeechSettings
from homeaudio.vcal.event_notifications import AUDIO_CACHE_DIR
from homeaudio.audio.filepath import modify_path
from homeaudio.audio.sound import change_speed

DEFAULT_ANNOUCEMENT_FILE = "audio_resources/default_announcement.mp3"

MORNING_ANNOUNCEMENT_FILE = "/tmp/morning_announcement.wav"
TTS_RETRY_DELAY_SECONDS = 2
TTS_MAX_ATTEMPTS = 3

logger = logging.getLogger(__name__)


class TextToSpeechError(Exception):
    """Raised when TTS generation fails after all retry attempts."""


class TextToSpeechRateLimitError(TextToSpeechError):
    """Raised when the TTS API responds with HTTP 429."""


"""
Converts text to a voice file and saves it to the cache directory.
Returns the path to the saved audio file.
"""
def text_to_voice_file(text, tld: str| None = None, speed: float | None = None, word_limit=1000, audio_cache_directory=AUDIO_CACHE_DIR):
    tld = tld or gtts_tld()
    speed = speed or gtts_speed()
    logger.debug(f"Converting text to speech with TLD {tld}: {text}")

    if word_limit is not None:
        words = text.split()
        text_to_say = " ".join(words[:word_limit])
    else:
        text_to_say = text

    audio_file_path = _get_file_path_for_text(text_to_say, tld, audio_cache_directory)
    speed_changed_audio_file_path = modify_path(audio_file_path, part=f"speed_{str(speed).replace('.', '_')}", suffix="wav") if not speed == 1.0 else audio_file_path

    # if the file already exists and isn't a leftover empty/corrupt write, return it
    if os.path.exists(speed_changed_audio_file_path) and os.path.getsize(speed_changed_audio_file_path) > 0:
        logger.debug("Audio file already exists for text: %s, returning existing file: %s", text_to_say, speed_changed_audio_file_path)
        return speed_changed_audio_file_path

    # if the file already exists and isn't a leftover empty/corrupt write, use it
    if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
        logger.debug("Audio file already exists for text: %s, using existing file: %s", text_to_say, audio_file_path)
    else:
        _download_tts_file(tld, text_to_say, audio_file_path)

    if not speed == 1.0:
        try:
            change_speed(audio_file_path, speed_changed_audio_file_path, speed)
        except Exception as e:
            logger.error("Failed to change speed of %s, using original file. Error: %s", audio_file_path, e)
            return audio_file_path

    return speed_changed_audio_file_path


def _download_tts_file(tld, text_to_say, audio_file_path):
    tmp_file_path = audio_file_path + ".tmp"
    max_attempts = TTS_MAX_ATTEMPTS
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug("Generating TTS for text: %s, saving to: %s (attempt %d/%d)", text_to_say, audio_file_path, attempt, max_attempts)
            tts = gTTS(text_to_say, timeout=5, lang=GOOGLE_TRANSLATE_LANG, tld=tld)

            # Ensure the cache directory exists
            os.makedirs(os.path.dirname(audio_file_path), exist_ok=True)
            tts.save(tmp_file_path)
            if os.path.getsize(tmp_file_path) == 0:
                raise ValueError("gTTS produced an empty file")
            os.replace(tmp_file_path, audio_file_path)
            return audio_file_path
        except (gTTSError, ValueError, ConnectionError) as e:
            last_error = e
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
            if _is_rate_limited(e):
                raise TextToSpeechRateLimitError(f"Rate limited by TTS API for text: {text_to_say!r}") from e
            logger.error(f"Error generating TTS for text: {text_to_say} (attempt {attempt}/{max_attempts}). Error: {e}")
            if attempt < max_attempts:
                time.sleep(TTS_RETRY_DELAY_SECONDS)

    raise TextToSpeechError(f"Failed to generate TTS after {max_attempts} attempts for text: {text_to_say!r}") from last_error

def _is_rate_limited(error: Exception) -> bool:
    return isinstance(error, gTTSError) and error.rsp is not None and error.rsp.status_code == 429

def _get_file_path_for_text(text, tld, cache_directory=AUDIO_CACHE_DIR):
    file_hash = hashlib.sha256(f"{text}_{tld}".encode("utf-8")).hexdigest()
    audio_file_path = os.path.join(cache_directory, file_hash + ".mp3")
    return audio_file_path

def gtts_tld(settings: GoogleTextToSpeechSettings | None = None) -> str:
    settings = settings or GoogleTextToSpeechSettings()
    options = ListOptionsSource("alternative_tlds", settings.alternative_tlds)
    return select_option_pseudorandomly(settings.default_tld,  settings.alternative_tld_probability, options) or DEFAULT_GOOGLE_TRANSLATE_TLD

def gtts_speed(settings: GoogleTextToSpeechSettings | None = None) -> float:
    settings = settings or GoogleTextToSpeechSettings()
    options = ListOptionsSource("alternative_speeds", [str(speed) for speed in settings.alternative_speeds])
    speed = select_option_pseudorandomly(str(settings.default_speed), settings.alternative_speed_probability, options)
    return float(speed) if speed else settings.default_speed

if __name__ == "__main__":
    test_text = "This is a test event. Don't do anything."
    audio_file = text_to_voice_file(test_text)
    print(f"Generated audio file: {audio_file}")