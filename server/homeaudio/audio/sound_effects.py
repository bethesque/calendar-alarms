import logging
import os
from homeaudio.env import SOUND_EFFECTS_DIRECTORY
from homeaudio.audio.random_text import FileListOptionsSource, select_text

logger = logging.getLogger(__name__)

class SoundEffectSelector:
    def __init__(self, sound_effect_probability: float, directory: str = SOUND_EFFECTS_DIRECTORY, extensions: list[str] = [".mp3"]):
        self.sound_effect_probability = sound_effect_probability
        self.options_source = FileListOptionsSource(directory=directory, extensions=extensions)

    def get_options_source(self):
        return self.options_source

    def get_random_sound_effect_file(self) -> str | None:
        selected = select_text(None, self.sound_effect_probability, self.options_source)
        if selected:
            logger.info(f"Selected random sound effect {selected} (probability {self.sound_effect_probability})")
            return selected
        else:
            logger.info(f"Random selection returned no sound effect (probability {self.sound_effect_probability})")
            return None

    def get_sound_effect_file(self, sound_effect: str | None) -> str | None:
        if sound_effect == "random":
            return self.get_random_sound_effect_file()
        elif sound_effect and sound_effect != "none":
            sound_effect_file_path = os.path.join(SOUND_EFFECTS_DIRECTORY, sound_effect)
            if os.path.isfile(sound_effect_file_path):
                logger.info(f"Using specified sound effect {sound_effect_file_path}")
                return sound_effect_file_path
            else:
                logger.warning(f"Sound effect file {sound_effect_file_path} does not exist. Skipping sound effect.")
                return None
        else:
            logger.info("No sound effect specified")
            return None
