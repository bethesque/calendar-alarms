from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from pydantic import field_validator
import yaml

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

    def save(self) -> None:
        path = Path(self.model_config["yaml_file"])
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w") as f:
            yaml.safe_dump(
                self.model_dump(mode="python"),
                f,
                sort_keys=True,
            )

class MainSettings(YAMLSettings):
    enabled: bool = Field(default=True)

    model_config = SettingsConfigDict(
        yaml_file="config/main.yaml"
    )

class MpdVolumeConfig(BaseModel):
    tts: int = Field(default=100, ge=0, le=100, title="TTS")
    talkie: int = Field(default=100, ge=0, le=100)
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
    tts: int = Field(default=80, ge=0, le=100, title="TTS")
    talkie: int = Field(default=80, ge=0, le=100)
    alarm: int = Field(default=100, ge=0, le=100, description="Alarm end volume")

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)

class SnapclientConfig(BaseModel):
    host: str
    volumes: VolumeConfig = Field(default_factory=VolumeConfig)

class SnapcastSettings(YAMLSettings):
    snapserver: str
    snapclients: list[SnapclientConfig] = Field(default_factory=list)
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
            for client in self.snapclients
        }

        return {
            host: volumes.get(host, self.default_volumes)[usecase]
            for host in hosts
        }


class CalendarSetting(BaseSettings):
    id: str
    name: str

class GoogleCalendarSettings(YAMLSettings):
    scope: str = Field(default="https://www.googleapis.com/auth/calendar.readonly", description="Permissions scope")
    redirect_server: str = Field(description="The local server to which the redirect should be sent after authentication with Google")
    login_hint: str = Field(description="The default email address to put in the login form")
    calendars: list[CalendarSetting] = Field(default_factory=list)

    def calendar_filter(self)-> list[tuple]:
        return [(cal.id, cal.name) for cal in self.calendars]

    model_config = SettingsConfigDict(
        yaml_file="config/google_calendar.yaml"
    )


class AppSettings(BaseSettings):
    main_settings: MainSettings = Field(default_factory=MainSettings, description="Main settings")
    mpd_settings: MpdSettings = Field(default_factory=MpdSettings, description="MPD settings")
    snapcast_settings: SnapcastSettings = Field(default_factory=SnapcastSettings, description="Snapcast settings")
    google_calendar_settings: GoogleCalendarSettings = Field(default_factory=GoogleCalendarSettings, description="Google Calendar settings")

    def save(self) -> None:
        print("Saving models")
        self.main_settings.save()
        self.mpd_settings.save()
        self.snapcast_settings.save()
        self.google_calendar_settings.save()
