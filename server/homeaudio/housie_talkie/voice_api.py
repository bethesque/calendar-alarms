import logging
import os
import threading
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile
from homeaudio.audio.scene import HomeAssistantScene
from homeaudio.audio.snapserver import Client
from homeaudio.housie_talkie.voice import play_audio_file_as_announcement
from homeaudio.housie_talkie.core import VoiceAnnouncementRequest, list_clients, list_sound_effects
from homeaudio.audio.settings import SnapcastSettings, SnapclientConfig

logger = logging.getLogger(__name__)

class ClientJson:
    def __init__(self, client: Client, client_config: SnapclientConfig | None):
        self.client = client
        self.client_config = client_config

    def to_dict(self) -> dict:
        return {
            "name": self.client.name,
            "display_name": self.client_config.display_name if self.client_config else self.client.name,
            "connected": self.client.connected
        }

def ensure_list_or_none(x) -> list | None:
    if isinstance(x, list):
        return x
    elif x is None:
        return None
    else:
        return [x]

class VoiceRoutes:
    def __init__(self):
        self.router = APIRouter()

        self.router.add_api_route(
            "",
            self.index,
            methods=["POST"],
            status_code=202
        )

        self.router.add_api_route(
            "/test",
            self.test,
            methods=["POST"],
            status_code=202
        )

        self.router.add_api_route(
            "/clients",
            self.clients,
            methods=["GET"],
        )

        self.router.add_api_route(
            "/sound-effects",
            self.sound_effects,
            methods=["GET"],
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

        players_list = ensure_list_or_none(players)

        talkie_request = VoiceAnnouncementRequest(
            audio_file=audio_file_path,
            scene=HomeAssistantScene(),
            sound_effect=sound_effect,
            player_names=players_list
        )

        logger.info(f"Received request to play voice recording {audio_file_path} as announcement with sound effect {sound_effect} to players {players_list}")

        threading.Thread(
            target=play_audio_file_as_announcement,
            args=(talkie_request,),
            daemon=True,
        ).start()

        return "OK"

    async def clients(self):
        snapcast_settings = SnapcastSettings()
        snapclient_configs = snapcast_settings.snapclients_by_name
        return {
            "clients": [ClientJson(client, snapclient_configs.get(client.name, None)).to_dict() for client in list_clients(snapcast_settings)]
        }

    async def sound_effects(self):
        return {
            "sound_effects": [
                {
                    "name": file,
                    "value": file
                }
                for file in list_sound_effects()
            ]
        }

    async def test(
        self,
        sound_effect: str | None = Form(None),
        players: list[str] | None = Form(None),
    ):
        audio_file_path = str(Path(__file__).resolve().parent.joinpath("audio").joinpath("test_recording.m4a"))
        players_list = ensure_list_or_none(players)

        logger.info(f"Received request to play test voice recording {audio_file_path} as announcement with sound effect {sound_effect} to players {players_list}")

        talkie_request = VoiceAnnouncementRequest(
            audio_file=audio_file_path,
            scene=HomeAssistantScene(),
            sound_effect=sound_effect,
            player_names=players_list
        )

        threading.Thread(
            target=play_audio_file_as_announcement,
            args=(talkie_request,),
            daemon=True,
        ).start()

        return "OK"
