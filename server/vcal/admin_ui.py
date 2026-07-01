from fastapi import APIRouter
from vcal.settings import AppSettings
from pydantic_ui import create_pydantic_ui, UIConfig

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
            ),
            data_saver=self._save_settings,
            data_loader=lambda: AppSettings()
        )

        self.router.include_router(self.ui_router)

    def _save_settings(self, data: dict):
        validated = AppSettings.model_validate(data)
        validated.save()
        return validated
