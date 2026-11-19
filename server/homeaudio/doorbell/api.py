from pathlib import Path
import threading
from fastapi import Response
from fastapi.responses import  FileResponse
from fastapi import APIRouter

from homeaudio.doorbell.core import start_doorbell
from homeaudio.vcal.core import stop_alarm

class DoorbellRoutes:
    def __init__(self):

        self.router = APIRouter()

        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route("", self.index, methods=["GET"])
        self.router.add_api_route("", self.play_doorbell, methods=["POST"])
        self.router.add_api_route("/stop", self.stop_doorbell, methods=["POST"])

    async def index(self):
        return FileResponse(Path(__file__).resolve().parent / "index.html")

    async def play_doorbell(self):
        success, message = start_doorbell()
        if success:
            return Response(content=f"Playing doorbell: {message}\n", status_code=202, media_type="text/plain")
        else:
            return Response(content=f"Could not play doorbell: {message}\n", status_code=500, media_type="text/plain")

    async def stop_doorbell(self):
        threading.Thread(
            target=stop_alarm,
            daemon=True,
        ).start()
        return Response(content="Stopping doorbell\n", status_code=202, media_type="text/plain")



