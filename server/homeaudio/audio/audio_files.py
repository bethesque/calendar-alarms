import logging
from dataclasses import dataclass
from pathlib import Path
from homeaudio.audio import SOUND_EFFECTS_ALLOWED_EXTENSIONS, WAKE_UP_ALARMS_ALLOWED_EXTENSIONS
from homeaudio.env import SOUND_EFFECTS_DIRECTORY, WAKE_UP_ALARM_ENABLED, WAKE_UP_ALARMS_DIRECTORY

logger = logging.getLogger(__name__)

DISABLED_SUFFIX = ".disabled"

class InvalidAudioFileName(ValueError):
    pass

class AudioFileNotFound(LookupError):
    pass

@dataclass
class AudioFile:
    name: str
    enabled: bool
    size: int

@dataclass
class AudioLibrary:
    slug: str
    title: str
    directory: str
    allowed_extensions: set[str]

def default_libraries() -> list[AudioLibrary]:
    libraries = [AudioLibrary("sound-effects", "Sound effects", SOUND_EFFECTS_DIRECTORY, SOUND_EFFECTS_ALLOWED_EXTENSIONS)]
    if WAKE_UP_ALARM_ENABLED:
        libraries.append(AudioLibrary("wake-up-alarms", "Wake up alarms", WAKE_UP_ALARMS_DIRECTORY, WAKE_UP_ALARMS_ALLOWED_EXTENSIONS))
    return libraries

def safe_file_name(file_name: str | None, allowed_extensions: set[str]) -> str:
    name = Path(file_name or "").name
    if not name or name != file_name or name.startswith("."):
        raise InvalidAudioFileName(f"Invalid file name {file_name!r}")
    if Path(name).suffix.lower() not in allowed_extensions:
        raise InvalidAudioFileName(f"Only {', '.join(sorted(allowed_extensions))} files are allowed")
    return name

class AudioFileManager:
    def __init__(self, library: AudioLibrary):
        self.library = library
        self.directory = Path(library.directory)

    def directory_exists(self) -> bool:
        return self.directory.is_dir()

    def list_files(self) -> list[AudioFile]:
        if not self.directory_exists():
            return []
        files = []
        for f in self.directory.iterdir():
            enabled = not f.name.endswith(DISABLED_SUFFIX)
            name = f.name if enabled else f.name.removesuffix(DISABLED_SUFFIX)
            if f.is_file() and Path(name).suffix.lower() in self.library.allowed_extensions:
                files.append(AudioFile(name, enabled, f.stat().st_size))
        return sorted(files, key=lambda f: f.name.lower())

    def existing_path(self, file_name: str) -> Path:
        path = self.directory / safe_file_name(file_name, self.library.allowed_extensions)
        disabled_path = path.with_name(path.name + DISABLED_SUFFIX)
        if path.is_file():
            return path
        if disabled_path.is_file():
            return disabled_path
        raise AudioFileNotFound(f"{file_name} not found")

    def save(self, files: list[tuple[str | None, bytes]]) -> list[str]:
        names = [safe_file_name(file_name, self.library.allowed_extensions) for file_name, _ in files]
        self.directory.mkdir(parents=True, exist_ok=True)
        for name, (_, content) in zip(names, files):
            target = self.directory / name
            logger.info(f"Saving uploaded audio file {target}")
            target.write_bytes(content)
            target.with_name(name + DISABLED_SUFFIX).unlink(missing_ok=True)
        return names

    def delete(self, file_name: str):
        path = self.existing_path(file_name)
        logger.info(f"Deleting audio file {path}")
        path.unlink()

    def toggle(self, file_name: str) -> bool:
        path = self.existing_path(file_name)
        enabled = path.name.endswith(DISABLED_SUFFIX)
        target = path.with_name(file_name if enabled else file_name + DISABLED_SUFFIX)
        logger.info(f"Renaming audio file {path} to {target.name}")
        path.rename(target)
        return enabled
