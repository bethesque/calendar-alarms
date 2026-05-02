import logging
import cherrypy
import google_auth_oauthlib.flow
from ecal.env import SERVER_ADDRESS, SCOPE, login_hint
from ecal.alarms.mpd import MpdClient, fade_out, mpd_connection
from ecal.music_assistant import MusicAssistantState
from ecal.env import MPD_HOST, MPD_PORT
from ecal.log_config import setup_logging_for_http_server
import threading
import time
from queue import Queue

setup_logging_for_http_server(logging.INFO)

logger = logging.getLogger(__name__)

class AlarmController(object):
    def __init__(self):
        self.queue = Queue(maxsize=1)  # <- key trick
        self._pending = False
        self._lock = threading.Lock()

        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            self.queue.get()
            try:
                self.stop_alarm()
            finally:
                with self._lock:
                    self._pending = False
                self.queue.task_done()

    def stop_alarm(self):
        # Stop alarm
        logger.info("Stopping alarm...")
        message = ""
        try:
            with mpd_connection() as alarm_player:
                if alarm_player.is_running():
                    fade_out([alarm_player], 3)
                    alarm_player.stop()
                    message = "Alarm stopped."
                else:
                    message = "MPD is not running. No alarm to stop."
        except Exception as e:
            logger.error(f"Error stopping alarm: {e}")

        logger.info(message)

        # Restore Music Assistant state
        try:
            if MusicAssistantState.fresh():
                ma = MusicAssistantState.load()
                ma.restore_original_state()
                logger.info("Restored saved Music Assistant state")
                MusicAssistantState.clear()
            else:
                logger.info("Not restoring Music Assistant state as the file is either too old or does not exist")
        except Exception as e:
            logger.error(f"Error restoring Music Assistant state: {e}")



    @cherrypy.expose
    def index(self):
        # HTML page with a single button
        return """
        <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
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

    @cherrypy.expose
    def stop(self):
        message = self.do_thing()
        cherrypy.response.status = 202

        return f"""
        <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Alarm Control</title>
            </head>
            <body>
                <h2>{message}</h2>
                <a href="/alarm">Go back</a>
            </body>
        </html>
        """

    def do_thing(self) -> str:
        with self._lock:
            if self._pending:
                return "Alarm currently being stopped"

            self._pending = True

        try:
            self.queue.put_nowait(None)
            return "Stopping alarm..."
        except:
            # extremely rare race safety net
            with self._lock:
                self._pending = False
            return "Alarm currently being stopped"

class CalendarWebServer(object):
    alarm = AlarmController()

    @cherrypy.expose
    def index(self):
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            "client_secret.json",
            scopes=[SCOPE],
            state="alwaysTheSame",
        )
        flow.redirect_uri = f"{SERVER_ADDRESS}/auth"

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state="alwaysTheSame",
            login_hint=login_hint,
            prompt="consent",
        )

        raise cherrypy.HTTPRedirect(authorization_url)

    @cherrypy.expose
    def auth(self, code=None, state=None, error=None, **kwargs):
        if state != "alwaysTheSame":
            return f"Something is up with your state: {state}"
        if error:
            return f"Something went wrong! {error}"
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            "client_secret.json",
            scopes=[SCOPE],
            state=state,
        )
        flow.redirect_uri = f"{SERVER_ADDRESS}/auth"
        flow.fetch_token(code=code)

        with open("token.json", "w") as text_file:
            print(flow.credentials.to_json(), file=text_file)

        return "The Calendar Alarms credentials have been updated."

if __name__ == "__main__":
    cherrypy.quickstart(CalendarWebServer(), config="server.conf")
