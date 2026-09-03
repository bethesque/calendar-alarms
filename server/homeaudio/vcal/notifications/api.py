import logging
from pathlib import Path
import threading
from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from homeaudio.vcal.morning_announcements import play_morning_announcements
from homeaudio.audio.scene import scene_for_env
from homeaudio.vcal.notifications.core import stop_alarm, test_alarm, mute_alarm_for_area_of_player, replay_last_notification, snooze_alarm
from homeaudio.vcal.notifications.events import get_all_event_notifications, get_all_events, get_calendar_refreshed_at
from homeaudio.vcal.cli import refresh_calendar_data
from homeaudio.env import HOME_ASSISTANT_SUPPORTED
from queue import Queue

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

class AlarmHandler:
    def __init__(self):
        self.queue = Queue(maxsize=1)
        self._pending = False
        self._lock = threading.Lock()

        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            action = self.queue.get()
            scene = scene_for_env().__class__
            try:
                if action.get("snooze", False):
                    snooze_alarm(scene.restore_after_alarm)
                else:
                    stop_alarm(scene.restore_after_alarm)
            finally:
                with self._lock:
                    self._pending = False
                self.queue.task_done()

    def stop_alarm(self, snooze: bool = False) -> str:
        with self._lock:
            if self._pending:
                return "Alarm currently being stopped/snoozed"

            self._pending = True

        try:
            self.queue.put_nowait({ "snooze": snooze } )
            return "Stopping alarm..."
        except Exception:
            with self._lock:
                self._pending = False
            return "Alarm currently being stopped/snoozed"

    def mute_area_of_player(self, player: str) -> str:
        threading.Thread(target=mute_alarm_for_area_of_player, args=(player,), daemon=True).start()
        return f"Muting area for {player}"


    def test_alarm(self) -> str:
        threading.Thread(target=test_alarm, daemon=True).start()
        return "Testing alarm..."

    def play_morning_announcements(self) -> str:
        threading.Thread(target=play_morning_announcements, daemon=True).start()
        return "Playing morning announcements..."

    def refresh_calendar_data(self) -> str:
        refresh_calendar_data()
        return "Calendar data refreshed"

    def replay_last_notification(self) -> str:
        threading.Thread(target=replay_last_notification, daemon=True).start()
        return "Replaying last notification"

class AlarmRoutes:
    def __init__(self):
        self.alarm_handler = AlarmHandler()
        self.router = APIRouter()

        self.router.add_api_route("/", self.index, methods=["GET"], name="alarm_index")

        self.router.add_api_route(
            "/stop",
            self.stop_alarm_endpoint,
            methods=["POST"],
            name="alarm_stop",
        )

        self.router.add_api_route(
            "/mute/area-of/{player}",
            self.mute_area_endpoint,
            methods=["POST"],
            name="alarm_mute",
        )

        self.router.add_api_route(
            "/test",
            self.test_alarm_endpoint,
            methods=["POST"],
            name="alarm_test",
        )

        self.router.add_api_route(
            "/morning-announcements",
            self.play_morning_announcements_endpoint,
            methods=["POST"],
            name="play_morning_announcements",
        )

        self.router.add_api_route(
            "/refresh-calendar-data",
            self.refresh_calendar_data_endpoint,
            methods=["POST"],
            name="refresh_calendar_data",
        )

        self.router.add_api_route(
            "/calendar-refreshed-at",
            self.calendar_refreshed_at_endpoint,
            methods=["GET"],
            name="calendar_refreshed_at",
        )

        self.router.add_api_route(
            "/notifications",
            self.notifications,
            methods=["GET"],
            name="notifications",
        )

        self.router.add_api_route(
            "/events",
            self.events,
            methods=["GET"],
            name="events",
        )

        self.router.add_api_route(
            "/replay",
            self.replay_last_notification,
            methods=["POST"],
            name="replay_last_notification",
        )

        self.router.add_api_route(
            "/snooze",
            self.snooze_endpoint,
            methods=["POST"],
            name="alarm_snooze",
        )

    async def index(self):
        return FileResponse(Path(__file__).resolve().parent / "index.html")

    async def stop_alarm_endpoint(self):
        message = self.alarm_handler.stop_alarm()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def mute_area_endpoint(self, player: str):
        message = self.alarm_handler.mute_area_of_player(player)
        return Response(content=message, status_code=202, media_type="text/plain")

    async def test_alarm_endpoint(self):
        message = self.alarm_handler.test_alarm()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def play_morning_announcements_endpoint(self):
        message = self.alarm_handler.play_morning_announcements()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def refresh_calendar_data_endpoint(self):
        message = self.alarm_handler.refresh_calendar_data()
        return Response(content=message, status_code=200, media_type="text/plain")

    async def calendar_refreshed_at_endpoint(self):
        refreshed_at = get_calendar_refreshed_at()
        return Response(content=refreshed_at.isoformat() if refreshed_at else "", status_code=200, media_type="text/plain")

    async def notifications(self, request: Request):
        event_notifications = sorted(get_all_event_notifications(), key=lambda notification: notification.notification_time)
        return templates.TemplateResponse(
            request=request,
            name="notifications.html",
            context={"notifications": event_notifications},
        )

    async def events(self, request: Request):
        events = get_all_events()
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context={"events": events},
        )

    async def replay_last_notification(self):
        message = self.alarm_handler.replay_last_notification()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def snooze_endpoint(self):
        message = self.alarm_handler.stop_alarm(snooze=True)
        return Response(content=message, status_code=202, media_type="text/plain")
