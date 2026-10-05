from fastapi import APIRouter, Depends, Request
from homeaudio.audio.settings import AppSettings, GoogleCalendarSettings
from homeaudio.env import GOOGLE_TRANSLATE_TLD_OPTIONS, HOME_ASSISTANT_SUPPORTED, HOUSIE_TALKIE_ENABLED, SNAPCAST_ENABLED, WAKE_UP_ALARM_ENABLED
from pydantic_ui import create_pydantic_ui, UIConfig, FieldConfig, DisplayConfig, Renderer, ActionButton

from homeaudio.env import APP_NAME

class AdminRoutes:
    def __init__(self):
        self.router = APIRouter()

        settings = AppSettings()
        self.calendar_select_props = {"options": self._calendar_options(settings.google_calendar_settings)}

        self.ui_router = create_pydantic_ui(
            AppSettings,
            prefix="",
            ui_config=UIConfig(
                title=f"{APP_NAME} Settings",
                show_validation=True,
                show_save_reset=True,
                show_types=False,
                footer_text="Home",
                footer_url="/",
                actions=[
                    ActionButton(id="home", label="Home", variant="outline", icon="arrow-left"),
                ],
                attr_configs=self.attr_configs(settings),
            ),
            data_saver=self._save_settings,
            data_loader=lambda: AppSettings()
        )

        @self.ui_router.action("home")
        async def home_action(data: dict, controller):
            await controller.navigate_to("/", new_tab=False)

        self.router.include_router(self.ui_router, dependencies=[Depends(self._refresh_calendar_options)])

    def _calendar_options(self, google_calendar_settings: GoogleCalendarSettings):
        return [ { "value": c.id, "label": c.name } for c in google_calendar_settings.calendars ]

    def _refresh_calendar_options(self, request: Request):
        # The schema is rebuilt per request from these props, so updating them in place keeps the select current.
        if request.url.path.endswith("/api/schema"):
            self.calendar_select_props["options"] = self._calendar_options(GoogleCalendarSettings())

    def attr_configs(self, settings: AppSettings):

        tld_options = [ { "value": tld, "label": tld } for tld in GOOGLE_TRANSLATE_TLD_OPTIONS ]

        return {
                    "google_calendar_settings.calendars.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{name}",
                            subtitle="{id}"
                        )
                    ),
                    "google_calendar_settings.token_file": FieldConfig(
                        renderer=Renderer.FILE_UPLOAD,
                        props={"accept": ".json,application/json"},
                    ),
                    "event_notification_settings.notification_rules.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{label}",
                            subtitle="{notification_type}"
                        )
                    ),
                    "event_notification_settings.notification_rules.[].calendar_id": FieldConfig(
                        display=DisplayConfig(
                            title="Calendar"
                        ),
                        renderer=Renderer.SELECT,
                        props=self.calendar_select_props
                    ),
                    "snapcast_settings": FieldConfig(
                        visible_when=f"{str(SNAPCAST_ENABLED).lower()} == true"
                    ),
                    "snapcast_settings.snapclients.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{display_name}",
                            subtitle="{area}",
                        ),
                    ),
                    "home_assistant_settings": FieldConfig(
                        visible_when=f"{str(HOME_ASSISTANT_SUPPORTED).lower()} == true"
                    ),
                    "home_assistant_settings.players.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{name}",
                            subtitle="{area}"
                        )
                    ),
                    "morning_announcements_settings.facts.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{text}",
                            subtitle="enabled: {enabled}"
                        )
                    ),
                    "morning_announcements_settings.schedule.weekdays": FieldConfig(
                        placeholder="HH:MM:SS",
                        display=DisplayConfig(
                            title="Weekdays",
                            subtitle="When to play the morning announcements on weekdays (24 hour time format, eg 07:17:00 for 7:17am)",
                        )
                    ),
                    "morning_announcements_settings.schedule.weekends": FieldConfig(
                        placeholder="HH:MM:SS",
                        display=DisplayConfig(
                            title="Weekends",
                            subtitle="When to play the morning announcements on weekends (24 hour time format, eg 07:17:00 for 7:17am)",
                        ),
                    ),
                    "morning_announcements_settings.schedule.holidays": FieldConfig(
                        placeholder="HH:MM:SS",
                        display=DisplayConfig(
                            title="Holidays",
                            subtitle="When to play the morning announcements on holidays (24 hour time format, eg 07:17:00 for 7:17am)",
                        ),
                    ),
                    "morning_announcements_settings.prelude_options.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{text}",
                            subtitle="enabled: {enabled}"
                        )
                    ),
                    "school_announcements_settings.schedule.weekdays": FieldConfig(
                        placeholder="HH:MM:SS",
                        display=DisplayConfig(
                            title="Weekdays",
                            subtitle="When to play the school announcement on weekdays (24 hour time format, eg 08:30:00 for 8:30am)",
                        )
                    ),
                    "housie_talkie_settings": FieldConfig(
                        visible_when=f"{str(HOUSIE_TALKIE_ENABLED).lower()} == true"
                    ),
                    "mpd_settings.volumes.wake_up_alarm_end": FieldConfig(
                        visible_when=f"{str(WAKE_UP_ALARM_ENABLED).lower()} == true"
                    ),
                    "mpd_settings.volumes.voice": FieldConfig(
                        visible_when=f"{str(HOUSIE_TALKIE_ENABLED).lower()} == true"
                    ),
                    "google_text_to_speech_settings.default_tld": FieldConfig(
                        renderer=Renderer.SELECT,
                        props={
                            "options": tld_options
                        }
                    ),
                    "google_text_to_speech_settings.alternative_tlds": FieldConfig(
                        renderer=Renderer.MULTI_SELECT,
                        props={
                            "options": tld_options
                        }
                    ),
                    "departure_notification_settings.api_key": FieldConfig(
                        renderer=Renderer.PASSWORD
                    ),
                }

    def _save_settings(self, data: dict):
        validated = AppSettings.model_validate(data)
        validated.save()
        return validated
