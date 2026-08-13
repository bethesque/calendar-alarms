import logging
from pathlib import Path
import threading
from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from vcal.morning_announcements import play_morning_announcements
from vcal.scene import Scene
from vcal.notifications.alarm import stop_alarm, test_alarm
from vcal.cli import refresh_calendar_data
from queue import Queue

logger = logging.getLogger(__name__)

class AlarmHandler:
    def __init__(self):
        self.queue = Queue(maxsize=1)
        self._pending = False
        self._lock = threading.Lock()

        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            self.queue.get()
            try:
                stop_alarm(Scene.restore_after_alarm)
            finally:
                with self._lock:
                    self._pending = False
                self.queue.task_done()

    def stop_alarm(self) -> str:
        with self._lock:
            if self._pending:
                return "Alarm currently being stopped"

            self._pending = True

        try:
            self.queue.put_nowait(None)
            return "Stopping alarm..."
        except Exception:
            with self._lock:
                self._pending = False
            return "Alarm currently being stopped"


    def test_alarm(self) -> str:
        threading.Thread(target=test_alarm, daemon=True).start()
        return "Testing alarm..."

    def play_morning_announcements(self) -> str:
        threading.Thread(target=play_morning_announcements, daemon=True).start()
        return "Playing morning announcements..."

    def refresh_calendar_data(self) -> str:
        threading.Thread(target=refresh_calendar_data, daemon=True).start()
        return "Refreshing calendar data..."

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

    async def index(self):
        return FileResponse(Path(__file__).resolve().parent / "index.html")

    async def stop_alarm_endpoint(self):
        message = self.alarm_handler.stop_alarm()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def test_alarm_endpoint(self):
        message = self.alarm_handler.test_alarm()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def play_morning_announcements_endpoint(self):
        message = self.alarm_handler.play_morning_announcements()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def refresh_calendar_data_endpoint(self):
        message = self.alarm_handler.refresh_calendar_data()
        return Response(content=message, status_code=202, media_type="text/plain")



