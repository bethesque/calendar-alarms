import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from pathlib import Path
from functools import partial
import logging
import http.client
from amixer_control import VolumeController
from snapserver import mute_client
from music_assistant import pause_player
from contextlib import contextmanager
import argparse

http.client.HTTPConnection.debuglevel = 1
logger = logging.getLogger(__name__)

"""
This service listens for POST requests to /audio/mute and mutes the audio output when triggered. It does this by:
1. Muting the ALSA output using amixer (via VolumeController) for an immediate response.
2. Muting the Snapclient by calling the Snapserver JSON-RPC API.
3. Pausing the Music Assistant player via Home Assistant webhook.
4. Restoring the ALSA volume gradually.
The service responds immediately to the HTTP request and performs the muting operations asynchronously to avoid blocking the client.
It uses only native Python libraries without any additional dependencies.
"""

def stop(audio_config):
    with muted_alsa():
        mute_snapclient(audio_config["snapserver_url"], audio_config["client_id_file"])
        pause_music_assistant_player(audio_config)

"""
For alarms/announcements, mute the snapclient rather than trying to stop the stream.
The next alarm/announcement will set the volume back to 100%.
"""
def mute_snapclient(ca_snapserver_rpc_url, client_id_file):
    try:
        client_id = Path(client_id_file).read_text().strip()
        if not client_id:
            logger.warning(f"No client ID found in {client_id_file}")
        else:
            mute_client(ca_snapserver_rpc_url, client_id)
    except Exception:
        logger.exception("Error muting snapclient")

def pause_music_assistant_player(audio_config):
    try:
        pause_player(audio_config["home_assistant_url"], audio_config["home_assistant_player_entity"])
    except Exception:
        logger.exception("Error pausing Music Assistant player")

@contextmanager
def muted_alsa():
    try:
        volume_controller = VolumeController()
        volume_controller.mute()
        yield
        volume_controller.unmute_slowly()
    except Exception:
        logger.exception("Exception muting/unmuting volume using amixer")


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, audio_config,  **kwargs):
        self.audio_config = audio_config
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path != "/audio/stop":
            self.send_response(404)
            self.end_headers()
            return

        # Respond immediately
        self.send_response(202)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Stopping\n")

        # Async execution
        threading.Thread(target=stop, args=(self.audio_config,), daemon=True).start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio control service")
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="The port to run the server on."
    )

    args = parser.parse_args()

    snapserver_url = os.environ["SNAPSERVER_RPC_URL"]
    client_id_file = os.environ["SNAPCLIENT_CLIENT_ID_FILE"]
    home_assistant_url = os.environ["HOME_ASSISTANT_URL"]
    home_assistant_player_entity = os.environ["HOME_ASSISTANT_PLAYER_ENTITY"]

    audio_config = {
        "snapserver_url": snapserver_url,
        "client_id_file": client_id_file,
        "home_assistant_url": home_assistant_url,
        "home_assistant_player_entity": home_assistant_player_entity
    }

    logger.info(f"Starting mute handler with config {audio_config}")

    handler_class = partial(Handler, audio_config=audio_config)

    HTTPServer(("0.0.0.0", args.port), handler_class).serve_forever()
