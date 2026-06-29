from fastapi import FastAPI
from vcal.settings import AppSettings
from pydantic_ui import create_pydantic_ui, DisplayConfig, FieldConfig, Renderer, UIConfig, PydanticUIController


# Create FastAPI app and mount pydantic-ui
app = FastAPI()

router = create_pydantic_ui(
        AppSettings,
        prefix="/config",
        ui_config=UIConfig(
            title="Calendar alarms configuration",
            show_validation=True,
            show_save_reset=True,
            show_types=False,
            footer_text="hello",
            xyz="foo"
        ),
        data_saver=lambda data: AppSettings.model_validate(data).save()
    )

app.include_router(router)

@router.action("save")
async def handle_save(data: dict, controller: PydanticUIController):
    """Save handler with Pydantic validation."""
    from pydantic import ValidationError

    print("HELLLOOOO")
    try:
        validated = AppSettings.model_validate(data)

        # save to file
        validated.save()

        await controller.show_toast("Settings saved!", "success")
        return {"saved": True}
    except ValidationError as e:
        await controller.show_toast(f"Validation error: {e}", "error")
        return {"saved": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_graceful_shutdown=1)
