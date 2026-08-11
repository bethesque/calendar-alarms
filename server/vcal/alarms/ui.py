import logging
import threading
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from vcal.announcements.morning_announcements import play_morning_announcements
from vcal.scene import Scene
from vcal.alarms.alarm import stop_alarm, test_alarm
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

        self.router.add_api_route(
            "",
            self.alarm_page,
            methods=["GET"],
            response_class=HTMLResponse,
            name="alarm_index"
        )

        self.router.add_api_route(
            "/stop",
            self.stop_alarm_endpoint,
            methods=["POST"],
            response_class=HTMLResponse,
            name="alarm_stop",
        )

        self.router.add_api_route(
            "/test",
            self.test_alarm_endpoint,
            methods=["POST"],
            response_class=HTMLResponse,
            name="alarm_test",
        )

        self.router.add_api_route(
            "/morning-announcements",
            self.play_morning_announcements_endpoint,
            methods=["POST"],
            response_class=HTMLResponse,
            name="play_morning_announcements",
        )

        self.router.add_api_route(
            "/refresh-calendar-data",
            self.refresh_calendar_data_endpoint,
            methods=["POST"],
            response_class=HTMLResponse,
            name="refresh_calendar_data",
        )

    async def alarm_page(self, request: Request):
        stop_url = request.url_for("alarm_stop")
        test_url = request.url_for("alarm_test")

        return self._alarm_form(None, request)

    async def stop_alarm_endpoint(self, request: Request):
        message = self.alarm_handler.stop_alarm()
        return self._alarm_form(message, request)

    async def test_alarm_endpoint(self, request: Request):
        message = self.alarm_handler.test_alarm()
        return self._alarm_form(message, request)

    async def play_morning_announcements_endpoint(self, request: Request):
        message = self.alarm_handler.play_morning_announcements()
        return self._alarm_form(message, request)


    async def refresh_calendar_data_endpoint(self, request: Request):
        message = self.alarm_handler.refresh_calendar_data()
        return self._alarm_form(message, request)


    def _alarm_form(self, message: str | None, request: Request):
        stop_url = request.url_for("alarm_stop")
        test_url = request.url_for("alarm_test")
        play_morning_announcements_url = request.url_for("play_morning_announcements")
        refresh_calendar_data_url = request.url_for("refresh_calendar_data")

        message_with_tags = f"<p>{message}</p>" if message else ""

        return f"""
        <html>
            <head>
                <meta name="viewport"
                      content="width=device-width, initial-scale=1.0">
                <title>Alarm Control</title>
                <link rel="stylesheet" href="/static/styles.css">
            </head>
            <body>
                <h1>Alarm Control</h1>
                {message_with_tags}
                <form method="post" action="{ stop_url }">
                    <button type="submit" class="stop">🔕 Stop Alarm</button>
                </form>
                <form method="post" action="{ test_url }" style="display:block; padding-top: 20px">
                    <button type="submit">Test Alarm</button>
                </form>
                <form method="post" action="{ play_morning_announcements_url }" style="display:block; padding-top: 20px">
                    <button type="submit">Play morning announcements</button>
                </form>
                <form method="post" action="{ refresh_calendar_data_url }" style="display:block; padding-top: 20px">
                    <button type="submit">Refresh calendar data</button>
                </form>
                <a href="/">Home</a>
            </body>
        </html>
        """