from pathlib import Path
import threading
import logging
from fastapi import Response
from fastapi.responses import  FileResponse
from fastapi import APIRouter

from homeaudio.vcal.wake_up_alarm.core import start_wake_up_alarm
from homeaudio.vcal.notifications.core import stop_alarm

class WakeUpAlarmRoutes:
    def __init__(self):

        self.router = APIRouter()

        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route("/", self.index, methods=["GET"])
        self.router.add_api_route("/", self.play_wake_up_alarm, methods=["POST"])
        self.router.add_api_route("/stop", self.stop_wake_up_alarm, methods=["POST"])

    async def index(self):
        return FileResponse(Path(__file__).resolve().parent / "index.html")

    async def play_wake_up_alarm(self):
        success, message = start_wake_up_alarm()
        if success:
            return Response(content=f"Playing wake up alarm: {message}\n", status_code=202, media_type="text/plain")
        else:
            return Response(content=f"Could not play wake up alarm: {message}\n", status_code=500, media_type="text/plain")

    async def stop_wake_up_alarm(self):
        threading.Thread(
            target=stop_alarm,
            daemon=True,
        ).start()
        return Response(content="Stopping wake up alarm\n", status_code=202, media_type="text/plain")



