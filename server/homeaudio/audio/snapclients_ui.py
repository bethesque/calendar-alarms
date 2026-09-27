from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from homeaudio.audio.settings import SnapcastSettings
from homeaudio.audio.snapserver import Client, Snapserver

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

def last_seen_datetime(client: Client) -> datetime | None:
    sec = client.last_seen.get("sec")
    if not sec:
        return None
    return datetime.fromtimestamp(sec + client.last_seen.get("usec", 0) / 1_000_000)

class SnapclientsRoutes:
    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route(
            "/snapclients",
            self.snapclients,
            methods=["GET"],
            response_class=HTMLResponse,
            name="snapclients",
        )

    def snapclients(self, request: Request):
        error = None
        clients = []
        try:
            snapserver = Snapserver(SnapcastSettings().snapserver_rpc_url)
            clients = [(client, last_seen_datetime(client)) for client in sorted(snapserver.get_clients(), key=lambda client: client.name.lower())]
        except Exception as e:
            error = str(e)

        return templates.TemplateResponse(
            request=request,
            name="snapclients.html",
            context={"clients": clients, "error": error},
        )
