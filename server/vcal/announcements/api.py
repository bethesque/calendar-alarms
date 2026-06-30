import argparse
from threading import Thread
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from vcal.announcements.announce import play_announcement, list_sound_effects
from vcal.scene import Scene

class AnnouncementRequest(BaseModel):
    message: Optional[str] = None
    sound_effect: Optional[str] = None
    players: Optional[list[str] | str] = None

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
