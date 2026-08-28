import argparse
import logging
import yaml
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic_settings import BaseSettings
from homeaudio.audio.log_config import setup_logging_for_http_server
from homeaudio.vcal.cal.ui import TokenRoutes
from homeaudio.housie_talkie.tts_api import TtsRoutes
from homeaudio.housie_talkie.voice_api import VoiceRoutes
from homeaudio.audio.admin_ui import AdminRoutes
from homeaudio.vcal.notifications.api import AlarmRoutes
from homeaudio.audio.logs_ui import CalendarAlarmsStatusRoutes, JournalctlRoutes, LogRoutes
from homeaudio.vcal.wake_up_alarm.api import WakeUpAlarmRoutes
from homeaudio.housie_talkie.ui import UserInterfaceRoutes
from homeaudio.audio.settings import SnapcastSettings
from homeaudio.env import APP_NAME, HOUSIE_TALKIE_ENABLED, WAKE_UP_ALARM_ENABLED

setup_logging_for_http_server(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    snapclient_settings = SnapcastSettings()
    housie_talkie_link = """<li><a href="/housie-talkie" class="button"><span class="emoji">🎤</span><span>Housie Talkie</span></a></li>""" if HOUSIE_TALKIE_ENABLED else ""
    wake_up_alarm_link = """<li><a href="/wake-up-alarm" class="button"><span class="emoji">⏰</span><span>Wake up alarm</a></span></li>""" if WAKE_UP_ALARM_ENABLED else ""
    return f"""
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{APP_NAME}</title>
            <link rel="stylesheet" href="/static/styles.css">
        </head>
        <body>
            <h1>{APP_NAME}</h1>
            <ul class="buttons">
                <li><a href="/alarm" class="button"><span class="emoji">📅</span><span>Calendar notifications<span></a></li>
                {housie_talkie_link}
                {wake_up_alarm_link}
            </ul>
            <ul class="buttons">
                <li><a href="/settings" class="button"><span class="emoji">⚙️</span><span>Settings</span></a></li>
                <li><a href="{snapclient_settings.snapserver}" class="button"><span class="emoji">🔊</span><span>Snapweb</span></a>
      </li>
            </ul>
            <ul class="buttons">
                <li><a href="/status/calendar-alarms-service"class="button" >Calendar Alarms HTTP Service Status</a></li>
                <li><a href="/logs/server" class="button">Calendar Alarms HTTP Server logs</a></li>
                <li><a href="/logs/data-refresh" class="button">Data Refresh logs</a></li>
                <li><a href="/logs/cron" class="button">Cron logs</a></li>
            </ul>
            <ul class="buttons">
                <li><a href="/logs/http" class="button">HTTP service journal</a></li>
                <li><a href="/logs/morning-announcements" class="button">Morning announcements journal</a></li>
                <li><a href="/logs/calendar-alarms" class="button">Calendar alarms journal</a></li>
            </ul>
        </body>
    </html>
    """

app.include_router(TokenRoutes("/alarm").router, prefix="/token")
app.include_router(TtsRoutes().router, prefix="/announce")
app.include_router(VoiceRoutes().router, prefix="/talkie")
app.include_router(UserInterfaceRoutes().router, prefix="/housie-talkie")
app.include_router(AlarmRoutes().router, prefix="/alarm")
app.include_router(WakeUpAlarmRoutes().router, prefix="/wake-up-alarm")
app.include_router(AdminRoutes().router, prefix="/settings")
app.include_router(CalendarAlarmsStatusRoutes().router, prefix="/status/calendar-alarms-service")
app.include_router(LogRoutes(file_path="logs/data_refresh.log", route="/data-refresh").router, prefix="/logs")
app.include_router(LogRoutes(file_path="logs/cron.log", route="/cron").router, prefix="/logs")
app.include_router(JournalctlRoutes(service_name="calendar-alarms-http", route="/http").router, prefix="/logs")
app.include_router(JournalctlRoutes(service_name="calendar-alarms-morning-announcements", route="/morning-announcements").router, prefix="/logs")
app.include_router(JournalctlRoutes(service_name="calendar-alarms", route="/calendar-alarms").router, prefix="/logs")
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":

    class SuppressPollFilter(logging.Filter):
        def filter(self, record):
            print("used")
            return "/events/poll" not in record.getMessage()

    class UvicornSettings(BaseSettings):
        host: str = "0.0.0.0"
        port: int = 8081
        ssl_certfile: str | None = None
        ssl_keyfile: str | None = None
        log_level: str = "info"
        timeout_graceful_shutdown: int = 1
        reload: bool = False
        access_log: bool = False

        def uvicorn_kwargs(self) -> dict:
            return self.model_dump(exclude_none=True)

    parser = argparse.ArgumentParser(description="Home audio control service")

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
