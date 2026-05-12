#from _socket import _RetAddress
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from socketserver import BaseServer
import threading
from urllib.request import Request, urlopen
from pathlib import Path
import argparse
from functools import partial
import logging
import http.client

http.client.HTTPConnection.debuglevel = 1
logger = logging.getLogger(__name__)

# Global lock to prevent concurrent mute operations
mute_lock = threading.Lock()


def mute_client(snapserver_rpc_url, client_id_file):
    logger.info(f"Muting, snapserver_rpc_url={snapserver_rpc_url}, client_id_file={client_id_file}")
    with mute_lock:
        try:
            client_id = Path(client_id_file).read_text().strip()
            if not client_id:
                logger.warning(f"No client ID found in {client_id_file}")
                return

            payload = {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "Client.SetVolume",
                "params": {
                    "id": client_id,
                    "volume": {
                        "muted": True,
                        "percent": 0
                    }
                }
            }

            req = Request(
                snapserver_rpc_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(req, timeout=5) as resp:
                resp.read()

        except Exception as e:
            print(f"mute_client error: {e}")


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, snapserver_rpc_url=None, client_id_file=None, **kwargs):
        self.snapserver_rpc_url = snapserver_rpc_url
        self.client_id_file = client_id_file
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path != "/alarm/mute":
            self.send_response(404)
            self.end_headers()
            return

        # Respond immediately
        self.send_response(202)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Muting\n")

        # Async execution
        threading.Thread(target=mute_client, args=(self.snapserver_rpc_url, self.client_id_file), daemon=True).start()

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio control service")
    parser.add_argument(
        "--snapserver_rpc_url",
        type=str,
        required=True,
        help="The Snapserver RPC URL"
    )

    parser.add_argument(
        "--client_id_file",
        type=str,
        required=True,
        help="The path to a text file containing the ID of the snapclient"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="The port to run the server on."
    )


    args = parser.parse_args()
    handler_class = partial(Handler, snapserver_rpc_url=args.snapserver_rpc_url, client_id_file=args.client_id_file)

    HTTPServer(("0.0.0.0", args.port), handler_class).serve_forever()
