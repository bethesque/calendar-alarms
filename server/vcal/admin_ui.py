from fastapi import APIRouter
from vcal.settings import AppSettings
from pydantic_ui import create_pydantic_ui, UIConfig, FieldConfig, Renderer

class AdminRoutes:
    def __init__(self):
        self.router = APIRouter()

        self.ui_router = create_pydantic_ui(
            AppSettings,
            prefix="",
            ui_config=UIConfig(
                title="Calendar alarms configuration",
                show_validation=True,
                show_save_reset=True,
                show_types=False,
                footer_text="hello",
                xyz="foo",
                attr_configs={
                    "google_calendar_settings.notification_rules.[].owner": FieldConfig(
                        renderer=Renderer.SELECT,
                        options_from="google_calendar_settings.calendars.[].name"
                    ),
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
