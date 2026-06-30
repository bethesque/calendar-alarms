import argparse
import logging
import threading
from queue import Queue

import google_auth_oauthlib.flow
import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from vcal.log_config import setup_logging_for_http_server
from vcal.scene import Scene
from vcal.alarms.alarm import stop_alarm
from vcal.announcements.index import AnnouncementController
from vcal.announcements.housie_talkie import HousieTalkieController
from vcal.settings import GoogleCalendarSettings

setup_logging_for_http_server(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI()

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

    def do_thing(self) -> str:
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


alarm_controller = AlarmHandler()
announce_controller = AnnouncementController()
talkie_controller = HousieTalkieController()


@app.get("/", include_in_schema=False)
def index():
    settings = GoogleCalendarSettings()

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=[settings.scope],
        state="alwaysTheSame",
    )

    flow.redirect_uri = f"{settings.redirect_server}/auth"

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state="alwaysTheSame",
        login_hint=settings.login_hint,
        prompt="consent",
    )

    return RedirectResponse(url=authorization_url)


@app.get("/auth")
def auth(code: str | None = None,
         state: str | None = None,
         error: str | None = None):
    settings = GoogleCalendarSettings()

    if state != "alwaysTheSame":
        return HTMLResponse(f"Something is up with your state: {state}")

    if error:
        return HTMLResponse(f"Something went wrong! {error}")

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=[settings.scope],
        state=state,
    )

    flow.redirect_uri = f"{settings.redirect_server}/auth"
    flow.fetch_token(code=code)

    with open("token.json", "w") as text_file:
        text_file.write(flow.credentials.to_json())

    return HTMLResponse(
        "The Calendar Alarms credentials have been updated."
    )


@app.get("/alarm", response_class=HTMLResponse)
def alarm_page():
    return """
    <html>
        <head>
            <meta name="viewport"
                  content="width=device-width, initial-scale=1.0">
            <title>Alarm Control</title>
        </head>
        <body>
            <h1>Alarm Control</h1>
            <form method="post" action="/alarm/stop">
                <button type="submit">Stop Alarm</button>
            </form>
        </body>
    </html>
    """


@app.post("/alarm/stop", response_class=HTMLResponse)
def stop_alarm_endpoint():
    message = alarm_controller.do_thing()

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
                <a href="/alarm">Go back</a>
            </body>
        </html>
        """,
        status_code=202,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio control service")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind to",
    )

    args = parser.parse_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )