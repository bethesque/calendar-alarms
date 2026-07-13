import logging
import os
import threading
from fastapi import APIRouter, File, Form, UploadFile
from vcal.scene import Scene
from vcal.announcements.announce import play_audio_file_as_announcement, AudioFileAnnouncementRequest

logger = logging.getLogger(__name__)

def ensure_list_or_none(x):
    if isinstance(x, list):
        return x
    elif x is None:
        return None
    else:
        return [x]

class HousieTalkieRoutes:
    def __init__(self):
        self.router = APIRouter()

        self.router.add_api_route(
            "",
            self.index,
            methods=["POST"],
            status_code=202
        )

    async def index(
        self,
        audio: UploadFile = File(...),
        sound_effect: str | None = Form(None),
        players: list[str] | None = Form(None),
    ):
        filename = audio.filename or "recording.m4a"
        audio_file_path = os.path.join(
            "/tmp",
            os.path.basename(filename),
        )

        with open(audio_file_path, "wb") as f:
            while chunk := await audio.read(65536):
                f.write(chunk)

        talkie_request = AudioFileAnnouncementRequest(
            audio_file=audio_file_path,
            scene=Scene(),
            sound_effect=sound_effect,
            player_names=ensure_list_or_none(players)
        )

        threading.Thread(
            target=play_audio_file_as_announcement,
            args=(talkie_request,),
            daemon=True,
        ).start()

        return "OK"
