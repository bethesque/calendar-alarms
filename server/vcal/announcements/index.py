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
