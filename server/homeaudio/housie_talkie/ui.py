from pathlib import Path
import threading
import logging
from fastapi import Response
from fastapi.responses import  FileResponse
from fastapi import APIRouter

from homeaudio.vcal.wake_up_alarm.core import start_wake_up_alarm
from homeaudio.vcal.notifications.core import stop_alarm

class UserInterfaceRoutes:
    def __init__(self):

        self.router = APIRouter()

        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route("/", self.index, methods=["GET"])

    async def index(self):
        return FileResponse(Path(__file__).resolve().parent / "index.html")
