from datetime import datetime
import logging
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, YamlConfigSettingsSource
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
        path = Path(self.model_config["yaml_file"]) # pyright: ignore[reportArgumentType, reportTypedDictNotRequiredAccess]
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
    voice: int = Field(default=100, ge=0, le=100, title="Voice recording volume")
    alarm_start: int = Field(default=50, ge=0, le=100, title="Event alarm start volume")
    alarm_end: int = Field(default=100, ge=0, le=100, title="Event alarm end volume")
    wake_up_alarm_end: int = Field(default=60, ge=0, le=100, title="Wake up alarm end volume")

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)

class MpdSettings(YAMLSettings):
    host: str = Field(default="/run/mpd/socket", description="The host or socket path by which to connect to the MPD process. Must match the configuration for bind_to_address in /etc/mpd.conf")
    port: int = Field(default=0, description="Set to 0 when using a socket.")
    volumes: MpdVolumeConfig = Field(default_factory=MpdVolumeConfig)

    model_config = SettingsConfigDict(
        yaml_file="config/mpd.yaml"
    )

class VolumeConfig(BaseModel):
    tts: int = Field(default=80, ge=0, le=100, title="TTS volume")
    voice: int = Field(default=80, ge=0, le=100, title="Voice recording volume")
    alarm: int = Field(default=100, ge=0, le=100, title="Alarm end volume")

    def __getitem__(self, key: str) -> int:
        return getattr(self, key)

class SnapclientConfig(BaseModel):
    name: str = Field(description="The config name or host name of the Snapclient")
    display_name: str = Field(description="The display name of the Snapclient")
    area: str | None = Field(default=None, description="The area of the house where the Snapclient's host is located")
    volumes: VolumeConfig = Field(default_factory=VolumeConfig)

class SnapcastSettings(YAMLSettings):
    snapserver: str
    snapclients: list[SnapclientConfig] = Field(default_factory=list)
    default_volumes: VolumeConfig = Field(default_factory=VolumeConfig)

    model_config = SettingsConfigDict(
        yaml_file="config/snapcast.yaml"
    )

    @property
    def snapserver_rpc_url(self):
        return self.snapserver + "/jsonrpc"

    def volumes_for_players(self, player_names, usecase: str) -> dict[str, int]:
        volumes = {
            client.name: client.volumes
            for client in self.snapclients
        }

        return {
            player_name: volumes.get(player_name, self.default_volumes)[usecase]
            for player_name in player_names
        }

    @property
    def snapclients_by_name(self):
        return {
            client.name: client
            for client in self.snapclients
        }

    def snapclients_for_area(self, area: str) -> list[SnapclientConfig]:
        return [snapclient for snapclient in self.snapclients if snapclient.area == area]

    def snapclient_settings(self, name: str) -> SnapclientConfig:
        return next((snapclient for snapclient in self.snapclients if snapclient.name == name))


class CalendarSetting(BaseModel):
    id: str
    name: str

class NotificationRule(BaseModel):
    pattern: str = Field(..., description="The substring to match in the event description")
    owner: str | None = Field(default=None, description="The event owner that must match for the rule to apply")
    notification_type: Literal["alarm", "announce"] = Field(default="alarm", description="The notification type: alarm or announce")
    offset_minutes: int = Field(default=0, ge=0, description="Minutes before the event start")
    reminder: str | None = None
    replace: bool = Field(default=False, description="When true, the reminder replaces the announcement text, otherwise it is appended.")


class AlarmSettings(BaseSettings):
    gentle_alarm_duration: int = Field(default=120, description="The number of seconds to play the gentle alarm", ge=0)
    aggressive_alarm_loops: int = Field(default=1, description="The number of times to play the aggressive alarm. 0 to disable.", ge=0)
    full_loops: int = Field(default=2, description="The number of times the gentle/aggressive alarm loops should be played", ge=1)

class NotificationSettings(YAMLSettings):
    notification_rules: list[NotificationRule] = Field(default_factory=list, description="Rules for creating notifications from event descriptions")
    alarms: AlarmSettings = Field(default_factory=AlarmSettings)

    model_config = SettingsConfigDict(
        yaml_file="config/notifications.yaml"
    )

class GoogleCalendarSettings(YAMLSettings):
    scope: str = Field(default="https://www.googleapis.com/auth/calendar.readonly", description="Permissions scope")
    redirect_server: str = Field(description="The local server to which the redirect should be sent after authentication with Google")
    login_hint: str = Field(description="The default email address to put in the login form")
    calendars: list[CalendarSetting] = Field(default_factory=list)
    notification_rules: list[NotificationRule] = Field(default_factory=list, description="Rules for creating notifications from event descriptions")

    def calendar_filter(self)-> list[tuple]:
        return [(cal.id, cal.name) for cal in self.calendars]

    model_config = SettingsConfigDict(
        yaml_file="config/google_calendar.yaml"
    )

class Option(BaseModel):
    text: str
    last_used: str | None = None
    enabled: bool | None = Field(default=True)

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
    prelude_options: list[Option] = Field(default_factory=list, description="Text to read after 'Good morning' and before the day's events")
    prelude_probability: float = Field(default=1, description="The probability that a prelude will be included")
    facts: list[Option] = Field(default_factory=list, description="List of facts to read after the day's events")

    model_config = SettingsConfigDict(
        yaml_file="config/morning_announcements.yaml"
    )

    @property
    def unused_facts(self) -> list[Option]:
        return [fact for fact in self.facts if fact.never_used() and fact.enabled]

    @property
    def enabled_prelude_options(self) -> list[Option]:
        return [prelude_option for prelude_option in self.prelude_options if prelude_option.enabled]

class MusicAssistantPlayer(BaseModel):
    name: str = Field(description="The name of the Music Assistant player in Home Assistant (excluding the 'media_player.' prefix)")
    area: str | None = Field(description="The area of the house where the Music Assistant player is located")

class HomeAssistantAnnouncementSettings(BaseModel):
    fade_volume: float = Field(default=0.15, description="The volume to fade the Music Assistant players to while playing an announcement", ge=0.0, le=1.0)
    fade_down_duration: float = Field(default=1.5, description="The number of seconds over which to fade down the audio playing on Music Assistant before an announcement.")
    fade_up_duration: float = Field(default=1.5, description="The number of seconds over which to fade down the audio playing on Music Assistant before an announcement.")

class HomeAssistantSettings(YAMLSettings):
    hass_url: str = Field(default="http://localhost:8095", description="The URL of the Home Assistant server", title="Home Assistant URL")
    hass_token: str = Field(default="", description="The API token for the Home Assistant server", title="Home Assistant Token")
    players: list[MusicAssistantPlayer] = Field(default_factory=list, description="List of Music Assistant players to dip volume for announcements")
    announcements: HomeAssistantAnnouncementSettings = Field(default_factory=HomeAssistantAnnouncementSettings)

    @property
    def player_names(self) -> list[str]:
        return [player.name for player in self.players]

    model_config = SettingsConfigDict(
        yaml_file="config/home_assistant.yaml"
    )

class HousieTalkieSettings(YAMLSettings):
    target_integrated_loudness: float = Field(default=-19.0, description="Target integrated loudness in LUFS", le=0)
    target_true_peak: float = Field(default=-1.5, description="Target true peak ceiling in dBTP", le=0)
    target_loudness_range: float = Field(default=1.0, description="Target loudness range in LU")

    model_config = SettingsConfigDict(
        yaml_file="config/housie_talkie.yaml"
    )

class AppSettings(BaseSettings):
    main_settings: MainSettings = Field(default_factory=MainSettings, description="Main settings")
    mpd_settings: MpdSettings = Field(default_factory=MpdSettings, description="MPD settings")
    snapcast_settings: SnapcastSettings = Field(default_factory=SnapcastSettings, description="Snapcast settings") # pyright: ignore[reportArgumentType]
    google_calendar_settings: GoogleCalendarSettings = Field(default_factory=GoogleCalendarSettings, description="Google Calendar settings") # type: ignore
    morning_announcements_settings: MorningAnnouncementsSettings = Field(default_factory=MorningAnnouncementsSettings, description="Morning announcements settings")
    home_assistant_settings: HomeAssistantSettings = Field(default_factory=HomeAssistantSettings, description="Home Assistant settings")
    housie_talkie_settings: HousieTalkieSettings = Field(default_factory=HousieTalkieSettings, description="Housie Talkie settings")
    notification_settings: NotificationSettings = Field(default_factory=NotificationSettings, description="Notification settings")

    def save(self) -> None:
        logger.info("Saving settings")
        self.main_settings.save()
        self.mpd_settings.save()
        self.snapcast_settings.save()
        self.google_calendar_settings.save()
        self.morning_announcements_settings.save()
        self.home_assistant_settings.save()
        self.housie_talkie_settings.save()
        self.notification_settings.save()
