import argparse
import cherrypy
from vcal.scene import Scene
from vcal.announcements.announce import play_announcement, list_sound_effects

class AnnouncementController(object):
    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    @cherrypy.tools.json_in()
    def index(self, **kwargs):

        json = cherrypy.request.json
        message = json.get("message", None)
        sound_effect = json.get("sound_effect", None)
        players = json.get("players", None)
        players = ensure_list(players) if players else None

        if message:
            import threading
            threading.Thread(target=play_announcement, args=(message, Scene(), sound_effect, players)).start()
            cherrypy.response.status = 202
            return "Announcement received"
        else:
            cherrypy.log("No message provided for announcement")
            cherrypy.response.status = 400
            return "Error: No message provided"


    @cherrypy.expose
    @cherrypy.tools.allow(methods=['GET'])
    @cherrypy.tools.json_out()
    def sound_effects(self, **kwargs):
        return list_sound_effects()



from threading import Thread
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel


from threading import Thread
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from vcal.scene import Scene

class AnnouncementRequest(BaseModel):
    message: Optional[str] = None
    sound_effect: Optional[str] = None
    players: Optional[list[str] | str] = None


class AnnouncementController2:
    def __init__(self):
        self.router = APIRouter()

        self.router.add_api_route(
            "",
            self.index,
            methods=["POST"],
            status_code=202,
        )

        self.router.add_api_route(
            "/sound_effects",
            self.sound_effects,
            methods=["GET"],
        )

    async def index(self, payload: AnnouncementRequest):
        if not payload.message:
            raise HTTPException(
                status_code=400,
                detail="No message provided",
            )

        players = (
            ensure_list(payload.players)
            if payload.players is not None
            else None
        )

        Thread(
            target=play_announcement,
            args=(
                payload.message,
                Scene(),
                payload.sound_effect,
                players,
            ),
            daemon=True,
        ).start()

        return "Announcement received"

    async def sound_effects(self):
        return list_sound_effects()

def ensure_list(x):
    if isinstance(x, list):
        return x
    return [x]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Basic CherryPy announcement server")
    parser.add_argument(
        "--conf",
        default="server.conf",
        help="CherryPy config file to use",
    )
    args = parser.parse_args()

    cherrypy.quickstart(AnnouncementController(), config=args.conf)
