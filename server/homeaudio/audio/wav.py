import logging
import os
from pathlib import Path
from homeaudio.env import CACHE_DIRECTORY, SOUND_EFFECTS_DIRECTORY, WAKE_UP_ALARMS_DIRECTORY
from homeaudio.vcal.event_notifications import AUDIO_DIRECTORY
from homeaudio.audio.sound import convert_mp3_to_wav

AUDIO_CACHE_DIR = Path(os.path.join(CACHE_DIRECTORY, "audio"))

logger = logging.getLogger(__name__)

def as_wav(file_path: str) -> str:
    if file_path.endswith(".wav"):
        return file_path
    else:
        wav_path = get_wav_cache_file_path(file_path)
        if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
            os.makedirs(Path(wav_path).parent, exist_ok=True)
            logger.debug(f"Converting {file_path} to {wav_path}")
            convert_mp3_to_wav(file_path, wav_path)

        return wav_path

def get_wav_cache_file_path(not_wav: str) -> str:
    not_wav_path = Path(not_wav)

    # already in cache, return same path with .wav
    if is_within_directory(not_wav_path, AUDIO_CACHE_DIR):
        return f"{not_wav_path.parent}/{not_wav_path.stem}.wav"

    for directory in [AUDIO_DIRECTORY, SOUND_EFFECTS_DIRECTORY, WAKE_UP_ALARMS_DIRECTORY]:
        if is_within_directory(not_wav_path, directory):
            relative_path = not_wav_path.parent.relative_to(directory)
            return str(AUDIO_CACHE_DIR.joinpath("audio_resources").joinpath(relative_path).joinpath(f"{not_wav_path.stem}.wav"))

    raise RuntimeError(f"Don't know how to make cache file path for {not_wav}")


def is_within_directory(not_wav_path: Path, directory: Path) -> bool:
    file_path = not_wav_path.resolve()
    directory = Path(directory).resolve()
    return directory in file_path.parents or file_path == directory