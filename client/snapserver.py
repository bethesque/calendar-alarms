import json
import threading
import logging
from urllib.request import Request, urlopen
import json
import urllib.request

logger = logging.getLogger(__name__)

# Global lock to prevent concurrent mute operations
mute_lock = threading.Lock()

def is_client_playing(ca_snapserver_rpc_url: str, client_id: str) -> bool:
    """Return True if the Snapclient is currently playing."""

    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "Server.GetStatus",
    }

    request = urllib.request.Request(
        ca_snapserver_rpc_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")

        data = json.load(response)

    status = data["result"]["server"]

    for group in status["groups"]:
        stream_id = group.get("stream_id")

        stream = next(
            (s for s in status["streams"] if s["id"] == stream_id),
            None,
        )

        if not stream:
            continue

        for client in group["clients"]:
            if client["id"] == client_id:
                return stream.get("status") == "playing"

    raise ValueError(f"Client '{client_id}' not found")

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
            logger.exception(f"mute_client error: {e}")
