import os
from pathlib import Path
import threading
import logging
import http.client
import re
import socket
import subprocess
import argparse
import requests
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI, BackgroundTasks, Response, Request
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse

from amixer_control import VolumeController
from snapserver import get_client_status, mute_client, get_playing_status
from music_assistant import pause_player, toggle_pause_play

from pydantic import Field
from pydantic_settings import BaseSettings
import yaml

STATIC_DIR = Path(__file__).parent / "static"

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
    home_assistant_url: str | None
    home_assistant_player_entity: str | None
    hostname: str = Field(default_factory=socket.gethostname)

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
            "home_assistant_url": self.home_assistant_url,
            "home_assistant_player_entity": self.home_assistant_player_entity,
            "hostname" : self.hostname
        }

def toggle(audio_config, params = None):
    with muted_alsa():
        is_snap_playing, client_id = _is_snapclient_playing(audio_config)
        if is_snap_playing:
            _mute_snapclient(audio_config, client_id)
        else:
            _toggle_music_assistant_player(audio_config)
    _report_battery_level(audio_config, params) if params else None


def stop(audio_config, params = None):
    with muted_alsa():
        _, client_id = get_playing_status(audio_config["snapserver_url"], audio_config["hostname"])
        _mute_snapclient(audio_config, client_id)
        _pause_music_assistant_player(audio_config)
    _report_battery_level(audio_config, params)

def _report_battery_level(audio_config, params):

    try:
        button_battery_level = float(params["button_battery_level"])
        logger.info(f"Reporting battery level {button_battery_level} to Home Assistant")
        url = f"{audio_config["home_assistant_url"]}/api/webhook/{audio_config["hostname"]}-flic-button-battery-level"
        try:
            response = requests.post(
                url,
                json={ "value": button_battery_level },
                timeout=10,
            )

            if not response.ok:
                logger.error(
                    "Failed to update battery level: HTTP %s - %s",
                    response.status_code,
                    response.text,
                )

        except requests.RequestException:
            logger.exception("Error sending battery level update")
    except (ValueError, TypeError):
        logger.info(f"Button battery level '{params["button_battery_level"]}' from headers is not a number, not reporting to Home Assistant")


def _is_snapclient_playing(audio_config) -> tuple[bool, str | None]:
    is_snapclient_playing = False
    client_id : str | None = None

    try:
        is_snapclient_playing, client_id = get_playing_status(audio_config["snapserver_url"], audio_config["hostname"])
    except Exception:
        logger.exception("Error checking if snapclient is playing")

    return is_snapclient_playing, client_id



"""
For alarms/announcements, mute the snapclient rather than trying to stop the stream.
The next alarm/announcement will set the volume back to 100%.
"""
def _mute_snapclient(audio_config, client_id):
    try:
        mute_client(audio_config["snapserver_url"], client_id)
    except Exception:
        logger.exception("Error muting snapclient")


def _toggle_music_assistant_player(audio_config):
    try:
        logger.info(f"Toggling pause/play Music Assistant player {audio_config['home_assistant_player_entity']} at {audio_config['home_assistant_url']} ")
        toggle_pause_play(audio_config["home_assistant_url"], audio_config["home_assistant_player_entity"])
    except Exception:
        logger.exception("Error toggling pause/play Music Assistant player")


def _pause_music_assistant_player(audio_config):
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


def run_in_background(target, audio_config, params):
    """Fire-and-forget execution, mirroring the original daemon-thread behaviour."""
    threading.Thread(target=target, args=(audio_config, params), daemon=True).start()


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
    snapclient_status = get_client_status(audio_config["snapserver_url"], audio_config["hostname"])

    return {
        "calendar-alarms-snapclient.service": {
            "status": system(["systemctl", "--user", "is-active", "calendar-alarms-snapclient.service"]),
        },
        "calendar-alarms-snapclient-status": snapclient_status,
        "sendspin-armv6.service": {
            "status": system(["systemctl", "--user", "is-active", "sendspin-armv6.service"])
        },
        "amixer": {"volume": amixer_volume}
    }

class AudioServer:
    def __init__(self, audio_config: dict):
        self.audio_config = audio_config
        self.app = FastAPI()
        self._operation_lock = threading.Lock()
        self._register_routes()

    def _register_routes(self):
        self.app.add_api_route("/audio/status", self.status, methods=["GET"])
        self.app.add_api_route("/audio/toggle", self.audio_toggle, methods=["POST"])
        self.app.add_api_route("/audio/stop", self.audio_stop, methods=["POST"])
        self.app.add_api_route("/audio", self.control_page, methods=["GET"])


    def _run_exclusive(self, background_tasks: BackgroundTasks, target, params):
        """Try to claim the lock; if busy, signal the caller to reject the request."""
        if not self._operation_lock.acquire(blocking=False):
            return False

        def _run_and_release():
            try:
                target(self.audio_config, params)
            finally:
                self._operation_lock.release()

        background_tasks.add_task(lambda: threading.Thread(target=_run_and_release, daemon=True).start())
        return True

    async def control_page(self):
        return FileResponse(STATIC_DIR / "index.html")

    async def status(self):
        try:
            body = _get_status_body(self.audio_config)
            return JSONResponse(status_code=200, content=body)
        except Exception:
            logger.exception("Error getting status")
            return PlainTextResponse("error", status_code=500)

    async def audio_toggle(self, background_tasks: BackgroundTasks, request: Request):
        button_battery_level = request.headers.get('button-battery-level', None)
        started = self._run_exclusive(background_tasks, toggle, {"button_battery_level": button_battery_level})
        if not started:
            return Response(content="Busy: another operation is in progress\n", status_code=409, media_type="text/plain")
        return Response(content="Toggling audio\n", status_code=202, media_type="text/plain")

    async def audio_stop(self, background_tasks: BackgroundTasks, request: Request):
        button_battery_level = request.headers.get('button-battery-level', None)
        started = self._run_exclusive(background_tasks, stop, {"button_battery_level": button_battery_level})
        if not started:
            return Response(content="Busy: another operation is in progress\n", status_code=409, media_type="text/plain")
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
