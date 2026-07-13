import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from pathlib import Path
from functools import partial
import logging
import http.client
from amixer_control import VolumeController
from snapserver import get_client_status, mute_client, is_client_playing
from music_assistant import pause_player, toggle_pause_play
from contextlib import contextmanager
import argparse
import socket

http.client.HTTPConnection.debuglevel = int(os.getenv("HTTP_LOG_LEVEL", "0") or 0) # 0: disabled, 1: enabled
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

def toggle(audio_config):
    with muted_alsa():
        snapclient_id = Path(client_id_file).read_text().strip() if Path(client_id_file).exists() else None
        is_snap_playing = is_snapclient_playing(audio_config, snapclient_id)

        if is_snap_playing:
            mute_snapclient(audio_config["snapserver_url"], snapclient_id)
        else:
            toggle_music_assistant_player(audio_config)

def stop(audio_config):
    with muted_alsa():
        snapclient_id = Path(client_id_file).read_text().strip() if Path(client_id_file).exists() else None
        mute_snapclient(audio_config["snapserver_url"], snapclient_id)
        pause_music_assistant_player(audio_config)


def is_snapclient_playing(audio_config, client_id):
    is_snapclient_playing = False
    if client_id:
        try:
            is_snapclient_playing = is_client_playing(audio_config["snapserver_url"], client_id)
        except Exception:
            logger.exception("Error checking if snapclient is playing")
    else:
        logger.warning(f"No client ID found in {client_id_file}, cannot determine if snapclient is playing")
    return is_snapclient_playing

"""
For alarms/announcements, mute the snapclient rather than trying to stop the stream.
The next alarm/announcement will set the volume back to 100%.
"""
def mute_snapclient(ca_snapserver_rpc_url, client_id):
    logger.info(f"Snapclient {client_id} is playing, muting snapclient at {ca_snapserver_rpc_url}")
    try:
        mute_client(ca_snapserver_rpc_url, client_id)
    except Exception:
        logger.exception("Error muting snapclient")

def toggle_music_assistant_player(audio_config):
    try:
        logger.info(f"Toggling pause/play Music Assistant player {audio_config['home_assistant_player_entity']} at {audio_config['home_assistant_url']} ")
        toggle_pause_play(audio_config["home_assistant_url"], audio_config["home_assistant_player_entity"])
    except Exception:
        logger.exception("Error toggling pause/play Music Assistant player")

def pause_music_assistant_player(audio_config):
    try:
        logger.info(f"Pausing Music Assistant player {audio_config['home_assistant_player_entity']} at {audio_config['home_assistant_url']} ")
        pause_player(audio_config["home_assistant_url"], audio_config["home_assistant_player_entity"])
    except Exception:
        logger.exception("Error toggling pause/play Music Assistant player")

@contextmanager
def muted_alsa():
    volume_controller = VolumeController()
    muted = False
    try:
        volume_controller.mute()
        muted = True
    except Exception:
        logger.exception("Exception muting volume using amixer")

    yield

    if muted:
        try:
            volume_controller.unmute_slowly()
        except Exception:
            logger.exception("Exception unmuting volume using amixer")


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, audio_config,  **kwargs):
        self.audio_config = audio_config
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/audio/status":
            return status(self, audio_config=self.audio_config)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/audio/stop" and self.path != "/audio/toggle":
            self.send_response(404)
            self.end_headers()
            return

        response = b"Toggling audio\n" if self.path == "/audio/toggle" else b"Stopping audio\n"

        # Respond immediately
        self.send_response(202)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(response)

        target = toggle if self.path == "/audio/toggle" else stop

        # Async execution
        threading.Thread(target=target, args=(self.audio_config,), daemon=True).start()

def status(handler: Handler, audio_config: dict):
    import subprocess
    import json
    import re

    try:
        def system(command: list[str]):
            try:
                return subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            except Exception:
                logger.exception(f"Error running command {command}")
                return "error"


        def write_response(body:str):
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(body.encode("utf-8"))

        amixer_result = system(["amixer"])
        match = re.search(r'Front Left: Playback (\d+) \[(\d+%)\]', amixer_result)
        amixer_volume = f"{match.group(1)} ({match.group(2)})" if match else None
        snapclient_status = get_client_status(audio_config["snapserver_url"], socket.gethostname())

        body = {
            "calendar-alarms-snapclient.service": {
                "status": system(["systemctl", "--user", "is-active", "calendar-alarms-snapclient.service"]),
                "snapclient_status": snapclient_status
            },
            "music-assistant-snapclient.service": {
                "status": system(["systemctl", "--user", "is-active", "music-assistant-snapclient.service"])
            },
            "sendspin-armv6.service": {
                "status": system(["systemctl", "--user", "is-active", "sendspin-armv6.service"])
            },
            "amixer": { "volume" : amixer_volume }
        }

        write_response(json.dumps(body))

    except Exception:
        logger.exception("Error getting status")
        handler.send_response(500)
        handler.end_headers()
        handler.wfile.write(b"error")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio control service")
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="The port to run the server on."
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="The host to run the server on."
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

    toggle_url = f"http://{args.host}:{args.port}/audio/toggle"
    stop_url = f"http://{args.host}:{args.port}/audio/stop"
    status_url = f"http://{args.host}:{args.port}/audio/status"
    logger.info(f"Starting audio client endpoints at {toggle_url}, {stop_url} and {status_url} with config {audio_config}")

    handler_class = partial(Handler, audio_config=audio_config)

    HTTPServer((args.host, args.port), handler_class).serve_forever()
