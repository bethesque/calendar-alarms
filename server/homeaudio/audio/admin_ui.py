from fastapi import APIRouter
from homeaudio.audio.settings import AppSettings
from homeaudio.env import HOME_ASSISTANT_SUPPORTED, HOUSIE_TALKIE_ENABLED
from pydantic_ui import create_pydantic_ui, UIConfig, FieldConfig, DisplayConfig, Renderer

from homeaudio.env import APP_NAME

class AdminRoutes:
    def __init__(self):
        self.router = APIRouter()

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
                attr_configs={
                    "google_calendar_settings.calendars.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{name}",
                            subtitle="{id}"
                        )
                    ),
                    "google_calendar_settings.notification_rules.[].owner": FieldConfig(
                        renderer=Renderer.SELECT,
                        options_from="google_calendar_settings.calendars.[].name"
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
                    "morning_announcements_settings.prelude_options.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{text}",
                            subtitle="enabled: {enabled}"
                        )
                    ),
                    "housie_talkie_settings": FieldConfig(
                        visible_when=f"{str(HOUSIE_TALKIE_ENABLED).lower()} == true"
                    ),
                    "event_notification_settings.notification_rules.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{pattern} @ {offset_minutes} minutes before",
                            subtitle="{notification_type}"

                        )
                    )
                },
            ),
            data_saver=self._save_settings,
            data_loader=lambda: AppSettings()
        )

        self.router.include_router(self.ui_router)

    def _save_settings(self, data: dict):
        validated = AppSettings.model_validate(data)
        validated.save()
        return validated
