from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from pydantic import field_validator



class YAMLSettings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            YamlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

class MainSettings(YAMLSettings):
    enabled: bool = Field(default=True)

    model_config = SettingsConfigDict(
        yaml_file="config/main.yaml"
    )

class MpdVolumeConfig(BaseModel):
    tts: int = Field(default=80, ge=0, le=100)
    talkie: int = Field(default=80, ge=0, le=100)
    alarm_start: int = Field(default=50, ge=0, le=100)
    alarm_end: int = Field(default=100, ge=0, le=100)

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)


class MpdSettings(YAMLSettings):
    volumes: MpdVolumeConfig = Field(default_factory=MpdVolumeConfig)

    model_config = SettingsConfigDict(
        yaml_file="config/mpd.yaml"
    )

class VolumeConfig(BaseModel):
    tts: int = Field(default=80, ge=0, le=100)
    talkie: int = Field(default=80, ge=0, le=100)
    alarm_start: int = Field(default=50, ge=0, le=100)
    alarm_end: int = Field(default=100, ge=0, le=100)

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)

class SnapclientConfig(BaseModel):
    host: str
    volumes: VolumeConfig = Field(default_factory=VolumeConfig)

class SnapcastSettings(YAMLSettings):
    snapserver: str
    snapclients: dict[str, SnapclientConfig] = Field(default_factory=dict)
    default_volumes: VolumeConfig = Field(default_factory=VolumeConfig)

    model_config = SettingsConfigDict(
        yaml_file="config/snapcast.yaml"
    )

    def snapserver_rpc_url(self):
        return self.snapserver + "/jsonrpc"

    # If no players specified, must use all players
    def volumes_for_players(self, hosts, usecase: str) -> dict[str, int]:
        volumes = {
            client.host: client.volumes
            for client in self.snapclients.values()
        }

        return {
            host: volumes.get(host, self.default_volumes)[usecase]
            for host in hosts
        }

    @field_validator("snapclients", mode="before")
    @classmethod
    def normalize_clients(cls, v):
        if not isinstance(v, dict):
            return {}

        out = {}
        for name, cfg in v.items():
            cfg = cfg or {}
            cfg.setdefault("host", name)
            out[name] = cfg

        return out

class Settings(BaseSettings):
    snapcast: dict[str, SnapclientConfig] = {}

