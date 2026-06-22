import argparse
import cherrypy
import os
import threading
from vcal.scene import Scene
from vcal.announcements.announce import play_audio_file_as_announcement
import logging

logger = logging.getLogger(__name__)

def background_task(filepath: str):
    play_audio_file_as_announcement(filepath, Scene())


class HousieTalkieController(object):
    @cherrypy.expose
    def index(self, audio):
        filename = getattr(audio, "filename", None) or "recording.m4a"
        dest = os.path.join("/tmp", os.path.basename(filename))

        with open(dest, "wb") as f:
            while chunk := audio.file.read(65536):
                f.write(chunk)

        threading.Thread(target=background_task, args=(dest,), daemon=True).start()

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
