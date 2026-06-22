import argparse
import cherrypy
import os
import threading
from vcal.scene import Scene
from vcal.announcements.announce import play_audio_file_as_announcement
import logging

logger = logging.getLogger(__name__)


def ensure_list(x):
    if isinstance(x, list):
        return x
    else:
        return [x]

class HousieTalkieController(object):
    @cherrypy.expose
    def index(self, audio, sound_effect, players):
        filename = getattr(audio, "filename", None) or "recording.m4a"
        audio_file_path = os.path.join("/tmp", os.path.basename(filename))

        with open(audio_file_path, "wb") as f:
            while chunk := audio.file.read(65536):
                f.write(chunk)

        threading.Thread(target=play_audio_file_as_announcement, args=(audio_file_path, Scene(), sound_effect, ensure_list(players)), daemon=True).start()

        cherrypy.response.status = 200
        return b"OK"



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HousieTalkie server")
    parser.add_argument(
        "--conf",
        default="server.conf",
        help="CherryPy config file to use",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    cherrypy.quickstart(HousieTalkieController(), config=args.conf)
