import argparse
import cherrypy
from vcal.scene import Scene2
from vcal.announcements.announce import play_announcement

class AnnouncementController(object):
    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    def index(self, message=None, **kwargs):

        if message:
            import threading
            threading.Thread(target=play_announcement, args=(message, Scene2())).start()
            cherrypy.response.status = 202
            return "Announcement received"
        else:
            cherrypy.log("No message provided for announcement")
            cherrypy.response.status = 400
            return "Error: No message provided"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Basic CherryPy announcement server")
    parser.add_argument(
        "--conf",
        default="server.conf",
        help="CherryPy config file to use",
    )
    args = parser.parse_args()

    cherrypy.quickstart(AnnouncementController(), config=args.conf)
