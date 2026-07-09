from datetime import datetime
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
from pydantic import field_validator
import yaml

logger = logging.getLogger(__name__)

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
    tts: int = Field(default=100, ge=0, le=100, title="TTS volume")
    talkie: int = Field(default=100, ge=0, le=100, title="Housie Talkie volume")
    alarm_start: int = Field(default=50, ge=0, le=100, title="Alarm start volume")
    alarm_end: int = Field(default=100, ge=0, le=100, title="Alarm end volume")

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)


class MpdSettings(YAMLSettings):
    volumes: MpdVolumeConfig = Field(default_factory=MpdVolumeConfig)

    model_config = SettingsConfigDict(
        yaml_file="config/mpd.yaml"
    )

class VolumeConfig(BaseModel):
    tts: int = Field(default=80, ge=0, le=100, title="TTS volume")
    talkie: int = Field(default=80, ge=0, le=100, title="Housie Talkie volume")
    alarm: int = Field(default=100, ge=0, le=100, description="Alarm end volume")

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)

class SnapclientConfig(BaseModel):
    host: str = Field(description="The hostname of the snapclient")
    area: str = Field(description="The area of the house where the snapclient is located")
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

class Option(BaseModel):
    text: str
    last_used: str | None = None

    def last_used_datetime(self) -> datetime | None:
        if self.last_used is None:
            return None
        return datetime.fromisoformat(self.last_used)

    def update_last_used(self, dt: datetime | None = None):
        dt = dt or datetime.now()
        self.last_used = dt.isoformat()

    def never_used(self) -> bool:
        return self.last_used is None

class MorningAnnouncementsSettings(YAMLSettings):
    prelude_options: list[str] = Field(default_factory=list, description="Text to read after 'Good morning' and before the day's events")
    prelude_probability: float = Field(default=1, description="The probability that a prelude will be included")
    facts: list[Option] = Field(default_factory=list, description="List of facts to read after the day's events")

    model_config = SettingsConfigDict(
        yaml_file="config/morning_announcements.yaml"
    )

    @property
    def unused_facts(self) -> list[Option]:
        return [fact for fact in self.facts if fact.never_used()]

class MusicAssistantPlayer(BaseModel):
    name: str = Field(description="The name of the Music Assistant player in Home Assistant (excluding the 'media_player.' prefix)")
    area: str = Field(description="The area of the house where the Music Assistant player is located")

class HomeAssistantSettings(YAMLSettings):
    hass_url: str = Field(default="http://localhost:8095", description="The URL of the Home Assistant server", title="Home Assistant URL")
    hass_token: str = Field(default="", description="The API token for the Home Assistant server", title="Home Assistant Token")
    players: list[MusicAssistantPlayer] = Field(default_factory=list, description="List of Music Assistant players to dip volume for announcements")

    @property
    def player_names(self) -> list[str]:
        return [player.name for player in self.players]

    model_config = SettingsConfigDict(
        yaml_file="config/home_assistant.yaml"
    )

class AppSettings(BaseSettings):
    main_settings: MainSettings = Field(default_factory=MainSettings, description="Main settings")
    mpd_settings: MpdSettings = Field(default_factory=MpdSettings, description="MPD settings")
    snapcast_settings: SnapcastSettings = Field(default_factory=SnapcastSettings, description="Snapcast settings")
    google_calendar_settings: GoogleCalendarSettings = Field(default_factory=GoogleCalendarSettings, description="Google Calendar settings")
    morning_announcements_settings: MorningAnnouncementsSettings = Field(default_factory=MorningAnnouncementsSettings, description="Morning announcements settings")
    home_assistant_settings: HomeAssistantSettings = Field(default_factory=HomeAssistantSettings, description="Home Assistant settings")

    def save(self) -> None:
        logger.info("Saving settings")
        self.main_settings.save()
        self.mpd_settings.save()
        self.snapcast_settings.save()
        self.google_calendar_settings.save()
        self.morning_announcements_settings.save()
        self.home_assistant_settings.save()
