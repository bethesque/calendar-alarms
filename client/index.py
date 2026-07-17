import os
import threading
import logging
import http.client
import re
import socket
import subprocess
import argparse
from pathlib import Path
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from amixer_control import VolumeController
from snapserver import get_client_status, mute_client, is_client_playing
from music_assistant import pause_player, toggle_pause_play

from pydantic import Field
from pydantic_settings import BaseSettings
import yaml

http.client.HTTPConnection.debuglevel = int(os.getenv("HTTP_LOG_LEVEL", "0") or 0)  # 0: disabled, 1: enabled
logger = logging.getLogger(__name__)

"""
This service listens for POST requests to /audio/mute and mutes the audio output when triggered. It does this by:
1. Muting the ALSA output using amixer (via VolumeController) for an immediate response.
2. Muting the Snapclient by calling the Snapserver JSON-RPC API.
3. Pausing the Music Assistant player via Home Assistant webhook.
4. Restoring the ALSA volume gradually.
The service responds immediately to the HTTP request and performs the muting operations asynchronously to avoid blocking the client.
"""

class Config(BaseSettings):
    port: int = Field(default=8080)
    host: str = Field(default="0.0.0.0")
    log_level: str = Field(default="info")
    snapserver_rpc_url: str | None
    snapclient_client_id_file: str | None
    home_assistant_url: str | None
    home_assistant_player_entity: str | None

    @property
    def uvicorn_kwargs(self) -> dict:
        return {
            "port": self.port,
            "host": self.host,
            "log_level": self.log_level
        }

    @property
    def app_config(self) -> dict:
        return {
            "snapserver_url": self.snapserver_rpc_url,
            "client_id_file": self.snapclient_client_id_file,
            "home_assistant_url": self.home_assistant_url,
            "home_assistant_player_entity": self.home_assistant_player_entity
        }

def toggle(audio_config):
    with muted_alsa():
        snapclient_id = Path(audio_config["client_id_file"]).read_text().strip() if Path(audio_config["client_id_file"]).exists() else None
        is_snap_playing = is_snapclient_playing(audio_config, snapclient_id)

        if is_snap_playing:
            mute_snapclient(audio_config["snapserver_url"], snapclient_id)
        else:
            toggle_music_assistant_player(audio_config)


def stop(audio_config):
    with muted_alsa():
        snapclient_id = Path(audio_config["client_id_file"]).read_text().strip() if Path(audio_config["client_id_file"]).exists() else None
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


def _run_in_background(target, audio_config):
    """Fire-and-forget execution, mirroring the original daemon-thread behaviour."""
    threading.Thread(target=target, args=(audio_config,), daemon=True).start()


def _get_status_body(audio_config: dict) -> dict:
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

    amixer_result = system(["amixer"])
    match = re.search(r'Front Left: Playback (\d+) \[(\d+%)\]', amixer_result)
    amixer_volume = f"{match.group(1)} ({match.group(2)})" if match else None
    snapclient_status = get_client_status(audio_config["snapserver_url"], socket.gethostname())

    return {
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
        "amixer": {"volume": amixer_volume}
    }


class AudioServer:
    """Encapsulates the FastAPI app and its routes for the audio control service."""

    def __init__(self, audio_config: dict):
        self.audio_config = audio_config
        self.app = FastAPI()
        self._register_routes()

    def _register_routes(self):
        self.app.add_api_route("/audio/status", self.status, methods=["GET"])
        self.app.add_api_route("/audio/toggle", self.audio_toggle, methods=["POST"])
        self.app.add_api_route("/audio/stop", self.audio_stop, methods=["POST"])

    async def status(self):
        try:
            body = _get_status_body(self.audio_config)
            return JSONResponse(status_code=200, content=body)
        except Exception:
            logger.exception("Error getting status")
            return PlainTextResponse("error", status_code=500)

    async def audio_toggle(self, background_tasks: BackgroundTasks):
        background_tasks.add_task(_run_in_background, toggle, self.audio_config)
        return Response(content="Toggling audio\n", status_code=202, media_type="text/plain")

    async def audio_stop(self, background_tasks: BackgroundTasks):
        background_tasks.add_task(_run_in_background, stop, self.audio_config)
        return Response(content="Stopping audio\n", status_code=202, media_type="text/plain")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Audio control service")

    parser.add_argument(
        "--conf",
        default="config.yaml",
    )

    args = parser.parse_args()

    with open(args.conf) as f:
        config = Config(**yaml.safe_load(f))

    uvicorn_args = config.uvicorn_kwargs

    parser = argparse.ArgumentParser(description="Audio control service")

    toggle_url = f"http://{config.host}:{config.port}/audio/toggle"
    stop_url = f"http://{config.host}:{config.port}/audio/stop"
    status_url = f"http://{config.host}:{config.port}/audio/status"
    logger.info(f"Starting audio client endpoints at {toggle_url}, {stop_url} and {status_url} with config {config.app_config}")

    server = AudioServer(config.app_config)

    uvicorn.run(server.app, host=config.host, port=config.port)
