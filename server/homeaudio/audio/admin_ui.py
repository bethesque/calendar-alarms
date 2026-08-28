from typing import Callable
from fastapi import APIRouter
from homeaudio.audio.settings import AppSettings, MorningAnnouncementsSchedule
from homeaudio.env import HOME_ASSISTANT_SUPPORTED, HOUSIE_TALKIE_ENABLED
from homeaudio.vcal.morning_announcements.timer import update_timer_unit
from pydantic_ui import create_pydantic_ui, UIConfig, FieldConfig, DisplayConfig, Renderer

from homeaudio.env import APP_NAME

class AdminRoutes:
    def __init__(self, morning_announcements_schedule_changed: Callable[[MorningAnnouncementsSchedule], None] = update_timer_unit):
        self.morning_announcements_schedule_changed = morning_announcements_schedule_changed
        self.router = APIRouter()

        settings = AppSettings()

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
                attr_configs=self.attr_configs(settings),
            ),
            data_saver=self._save_settings,
            data_loader=lambda: AppSettings()
        )

        self.router.include_router(self.ui_router)

    def attr_configs(self, settings: AppSettings):

        calendar_options = [ { "value": c.id, "label": c.name } for c in settings.google_calendar_settings.calendars ]

        return {
                    "google_calendar_settings.calendars.[]": FieldConfig(
                        display=DisplayConfig(
                            title="{name}",
                            subtitle="{id}"
                        )
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
                        props={
                            "options": calendar_options
                        }
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
                }

    def _save_settings(self, data: dict):
        previous = AppSettings()
        validated = AppSettings.model_validate(data)

        if previous.morning_announcements_settings.schedule != validated.morning_announcements_settings.schedule:
            self.morning_announcements_schedule_changed(validated.morning_announcements_settings.schedule)

        validated.save()
        return validated
