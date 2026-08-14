import argparse
import logging
import yaml
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic_settings import BaseSettings
from vcal.log_config import setup_logging_for_http_server
from vcal.cal.ui import GoogleCalendarAuthRoutes
from housie_talkie.tts_api import TtsRoutes
from housie_talkie.voice_api import VoiceRoutes
from vcal.admin_ui import AdminRoutes
from vcal.notifications.ui import AlarmRoutes
from vcal.logs_ui import CalendarAlarmsStatusRoutes, LogRoutes
from vcal.wake_up_alarm.api import WakeUpAlarmRoutes
from housie_talkie.ui import UserInterfaceRoutes

setup_logging_for_http_server(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    hostname = request.url.hostname
    return f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Tortice Home Audio</title>
            <link rel="stylesheet" href="/static/styles.css">
        </head>
        <body>
            <h1>Tortice Home Audio</h1>
            <ul class="buttons">
                <li><a href="/alarm" class="button"><span class="emoji">📅</span><span>Calendar notifications<span></a></li>
                <li><a href="/housie-talkie" class="button"><span class="emoji">🎤</span><span>Housie Talkie</span></a></li>
                <li><a href="/wake-up-alarm" class="button"><span class="emoji">⏰</span><span>Wake up alarm</a></span></li>
            </ul>
            <ul class="buttons">
                <li><a href="/settings" class="button"><span class="emoji">⚙️</span><span>Settings</span></a></li>
                <li><a href="http://nas.dixon.net.au:1880" class="button"><span class="emoji">🔊</span><span>Snapweb</span></a>
      </li>
            </ul>
            <ul class="buttons">
                <li><a href="/status/calendar-alarms-service"class="button" >Calendar Alarms HTTP Service Status</a></li>
                <li><a href="/logs/server" class="button">Calendar Alarms HTTP Server logs</a></li>
                <li><a href="/logs/alarms" class="button">Alarms logs</a></li>
                <li><a href="/logs/announcements" class="button">Announcements logs</a></li>
                <li><a href="/logs/data-refresh" class="button">Data Refresh logs</a></li>
                <li><a href="/logs/cron" class="button">Cron logs</a></li>
            </ul>
        </body>
    </html>
    """

app.include_router(GoogleCalendarAuthRoutes().router, prefix="")
app.include_router(TtsRoutes().router, prefix="/announce")
app.include_router(VoiceRoutes().router, prefix="/talkie")
app.include_router(UserInterfaceRoutes().router, prefix="/housie-talkie")
app.include_router(AlarmRoutes().router, prefix="/alarm")
app.include_router(WakeUpAlarmRoutes().router, prefix="/wake-up-alarm")
app.include_router(AdminRoutes().router, prefix="/settings")
app.include_router(CalendarAlarmsStatusRoutes().router, prefix="/status/calendar-alarms-service")
app.include_router(LogRoutes(file_path="logs/server.log", route="/server").router, prefix="/logs")
app.include_router(LogRoutes(file_path="logs/alarms.log", route="/alarms").router, prefix="/logs")
app.include_router(LogRoutes(file_path="logs/announcements.log", route="/announcements").router, prefix="/logs")
app.include_router(LogRoutes(file_path="logs/data_refresh.log", route="/data-refresh").router, prefix="/logs")
app.include_router(LogRoutes(file_path="logs/cron.log", route="/cron").router, prefix="/logs")
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":

    class SuppressPollFilter(logging.Filter):
        def filter(self, record):
            return "/events/poll" not in record.getMessage()

    class UvicornSettings(BaseSettings):
        host: str = "0.0.0.0"
        port: int = 8081
        ssl_certfile: str | None = None
        ssl_keyfile: str | None = None
        log_level: str = "info"
        timeout_graceful_shutdown: int = 1
        reload: bool = False

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

    logging.getLogger("uvicorn.access").addFilter(SuppressPollFilter())

    uvicorn.run("index:app", **uvicorn_args)
