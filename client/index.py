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



def mute(mute_config):
    with muted_alsa():
        mute_snapclient(mute_config["snapserver_url"], mute_config["client_id_file"])
        pause_music_assistant_player(mute_config)

def mute_snapclient(ca_snapserver_rpc_url, client_id_file):
    try:
        client_id = Path(client_id_file).read_text().strip()
        if not client_id:
            logger.warning(f"No client ID found in {client_id_file}")
        else:
            mute_client(ca_snapserver_rpc_url, client_id)
    except Exception:
        logger.exception("Error muting snapclient")

def pause_music_assistant_player(mute_config):
    try:
        pause_player(mute_config["home_assistant_url"], mute_config["home_assistant_token"], mute_config["home_assistant_player_entity"])
    except Exception:
        logger.exception("Error pausing Music Assistant player")


@contextmanager
def muted_alsa():
    try:
        volume_controller = VolumeController()
        #volume_controller.mute()
        yield
        #volume_controller.unmute_slowly()
    except Exception:
        logger.exception("Exception muting/unmuting volume using amixer")


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, mute_config,  **kwargs):
        self.mute_config = mute_config
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path != "/alarm/mute":
            self.send_response(404)
            self.end_headers()
            return

        # Respond immediately
        self.send_response(202)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Muting\n")

        # Async execution
        threading.Thread(target=mute, args=(self.mute_config,), daemon=True).start()

    def log_message(self, format, *args):
        return


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
    home_assistant_token = os.environ["HOME_ASSISTANT_TOKEN"]
    home_assistant_player_entity = os.environ["HOME_ASSISTANT_PLAYER_ENTITY"]

    mute_config = {
        "snapserver_url": snapserver_url,
        "client_id_file": client_id_file,
        "home_assistant_url": home_assistant_url,
        "home_assistant_token": home_assistant_token,
        "home_assistant_player_entity": home_assistant_player_entity
    }

    logger.info(f"Starting mute handler with config {mute_config}")

    handler_class = partial(Handler, mute_config=mute_config)

    HTTPServer(("0.0.0.0", args.port), handler_class).serve_forever()
