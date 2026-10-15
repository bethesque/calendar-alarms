from pathlib import Path

import pytest

from homeaudio.audio.settings import YAMLSettings


def _yaml_settings_classes(cls=YAMLSettings):
    for subclass in cls.__subclasses__():
        yield subclass
        yield from _yaml_settings_classes(subclass)


@pytest.fixture(autouse=True)
def isolate_yaml_settings(tmp_path, monkeypatch):
    """Points every YAMLSettings class at a temp dir so tests never read or write the real config/ dir."""
    config_dir = tmp_path / "config"
    for settings_class in _yaml_settings_classes():
        yaml_file = Path(settings_class.model_config["yaml_file"]).name # pyright: ignore[reportArgumentType, reportTypedDictNotRequiredAccess]
        monkeypatch.setitem(settings_class.model_config, "yaml_file", str(config_dir / yaml_file))
