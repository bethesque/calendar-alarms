import argparse
import logging
import yaml
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic_settings import BaseSettings
from vcal.log_config import setup_logging_for_http_server
from vcal.cal.ui import GoogleCalendarAuthRoutes
from vcal.announcements.api import AnnouncementRoutes
from vcal.announcements.housie_talkie import HousieTalkieRoutes
from vcal.admin_ui import AdminRoutes
from vcal.alarms.ui import AlarmRoutes

setup_logging_for_http_server(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
        <head>
            <meta name="viewport"
                  content="width=device-width, initial-scale=1.0">
            <title>Calendar Alarms</title>
            <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
            <h1>Calendar Alarms</h1>
            <ul>
                <li><a href="/login">Login</a></li>
                <li><a href="/alarm">Alarm</a></li>
                <li><a href="/admin">Admin</a></li>
            </ul>
        </body>
    </html>
    """

app.include_router(GoogleCalendarAuthRoutes().router, prefix="")
app.include_router(AnnouncementRoutes().router, prefix="/announce")
app.include_router(HousieTalkieRoutes().router, prefix="/talkie")
app.include_router(AlarmRoutes().router, prefix="/alarm")
app.include_router(AdminRoutes().router, prefix="/admin")
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":

    class UvicornSettings(BaseSettings):
        host: str = "0.0.0.0"
        port: int = 8081
        ssl_certfile: str | None = None
        ssl_keyfile: str | None = None
        log_level: str = "info"
        timeout_graceful_shutdown: int = 1


        def uvicorn_kwargs(self) -> dict:
            return self.model_dump(exclude_none=True)

    parser = argparse.ArgumentParser(description="Audio control service")

    parser.add_argument(
        "--conf",
        default="config/uvicorn.yaml",
    )

    args = parser.parse_args()

    uvicorn_args = {}

    if args.conf:
        with open(args.conf) as f:
            uvicorn_args = UvicornSettings(**yaml.safe_load(f)).uvicorn_kwargs()

    uvicorn.run(app, **uvicorn_args)
