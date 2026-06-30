from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import threading
from vcal.scene import Scene
from vcal.alarms.alarm import stop_alarm
from queue import Queue

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

    async def alarm_page(self, request: Request):
        stop_url = request.url_for("alarm_stop")

        return f"""
        <html>
            <head>
                <meta name="viewport"
                      content="width=device-width, initial-scale=1.0">
                <title>Alarm Control</title>
            </head>
            <body>
                <h1>Alarm Control</h1>
                <form method="post" action="{ stop_url }">
                    <button type="submit">Stop Alarm</button>
                </form>
                <a href="/">Home</a>
            </body>
        </html>
        """

    async def stop_alarm_endpoint(self, request: Request):
        message = self.alarm_handler.stop_alarm()
        alarm_index_url = request.url_for("alarm_index")

        return HTMLResponse(
            f"""
            <html>
                <head>
                    <meta name="viewport"
                          content="width=device-width, initial-scale=1.0">
                    <title>Alarm Control</title>
                </head>
                <body>
                    <h2>{message}</h2>
                    <a href="{alarm_index_url}">Go back</a>
                </body>
            </html>
            """,
            status_code=202,
        )