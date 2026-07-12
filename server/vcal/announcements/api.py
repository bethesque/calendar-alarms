import argparse
from threading import Thread
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from fastapi import Query
from pydantic import BaseModel
from vcal.announcements.announce import play_announcement, list_sound_effects, AnnouncementRequest
from vcal.scene import Scene

class HttpAnnouncementRequest(BaseModel):
    message: Optional[str] = None
    sound_effect: Optional[str] = None
    players: Optional[List[str]] = None

class AnnouncementRoutes:
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


    async def index(
        self,
        payload: Optional[HttpAnnouncementRequest] = None,
        message: Optional[str] = Query(None),
        sound_effect: Optional[str] = Query(None),
        players: Optional[List[str]] = Query(None),
    ):
        # Fall back to query string values if the JSON body didn't provide them
        message = (payload.message if payload else None) or message
        sound_effect = (payload.sound_effect if payload else None) or sound_effect
        players = (payload.players if payload and payload.players is not None else None) or players


        if not message:
            raise HTTPException(
                status_code=400,
                detail="No message provided",
            )

        players = ensure_list(players) if players is not None else None

        announcement_request = AnnouncementRequest(scene=Scene(), message=message, sound_effect=sound_effect, player_names=players)

        Thread(
            target=play_announcement,
            args=(
                announcement_request,
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
