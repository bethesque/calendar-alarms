import json
import threading
from urllib.request import Request, urlopen
import logging
import http.client

http.client.HTTPConnection.debuglevel = 1
logger = logging.getLogger(__name__)

# Global lock to prevent concurrent mute operations
mute_lock = threading.Lock()

def mute_client(ca_snapserver_rpc_url, client_id):
    logger.info(f"Muting, ca_snapserver_rpc_url={ca_snapserver_rpc_url}, client_id={client_id}")
    with mute_lock:
        try:


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
                ca_snapserver_rpc_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(req, timeout=5) as resp:
                resp.read()

        except Exception as e:
            print(f"mute_client error: {e}")
