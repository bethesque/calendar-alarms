import json
import threading
import logging
from urllib.request import Request, urlopen
import json
import urllib.request

logger = logging.getLogger(__name__)

# Global lock to prevent concurrent mute operations
mute_lock = threading.Lock()

def get_client_status(ca_snapserver_rpc_url: str, name: str) -> dict:
    """Return the status of the Snapclient."""
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

    matching_clients = []

    for group in status["groups"]:
        stream_id = group.get("stream_id")

        stream = next(
            (s for s in status["streams"] if s["id"] == stream_id),
            None,
        )

        if not stream:
            continue

        for client in group["clients"]:
            if client["config"].get("name", None) == name or client["host"].get("name", None) == name:
                matching_clients.append(client)

    if matching_clients:
        return max(matching_clients, key=lambda c: (c["lastSeen"]["sec"], c["lastSeen"]["usec"]))
    else:
        return {}



def get_playing_status(snapserver_rpc_url: str, name: str) -> tuple[bool, str]:
    """Return True if the Snapclient is currently playing."""

    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "Server.GetStatus",
    }

    request = urllib.request.Request(
        snapserver_rpc_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")

        data = json.load(response)

    status = data["result"]["server"]

    matching_clients = []

    for group in status["groups"]:
        stream_id = group.get("stream_id")

        stream = next(
            (s for s in status["streams"] if s["id"] == stream_id),
            None,
        )

        if not stream:
            continue

        for client in group["clients"]:
            if client["config"].get("name", None) == name or client["host"].get("name", None) == name:
                matching_clients.append(client | { "status": stream.get("status") })

    if matching_clients:
        client = max(matching_clients, key=lambda c: (c["lastSeen"]["sec"], c["lastSeen"]["usec"]))
        return client["status"] == "playing", client["id"]
    else:
        raise ValueError(f"Client '{name}' not found")



def mute_client(snapserver_rpc_url: str, client_id: str):
    logger.info(f"Muting Snapclient {client_id} at {snapserver_rpc_url}")
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
                snapserver_rpc_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(req, timeout=5) as resp:
                resp.read()

        except Exception as e:
            logger.exception(f"mute_client error: {e}")
