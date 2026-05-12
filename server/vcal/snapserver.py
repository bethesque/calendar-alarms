# vcal/snapserver.py

from typing import Any
import requests
import logging

logger = logging.getLogger(__name__)


class SnapserverError(Exception):
    pass

def set_clients_to_max_volume(snapserver_rpc_url):
    clients = get_clients(snapserver_rpc_url)

    logger.info("Connected clients:")
    for client in clients:
        logger.info(
            f"- {client['host']['name']} "
            f"({client['id']})"
        )

    results = set_all_client_volumes(
        SNAPSERVER_RPC_URL,
        percent=100,
    )

    logger.debug("\nVolume update results:")
    for result in results:
        logger.debug(result)

def _rpc_call(
    snapserver_rpc_url: str,
    method: str,
    params: dict[str, Any] | None = None,
    request_id: int = 1,
) -> dict[str, Any]:
    payload = {
        "id": request_id,
        "jsonrpc": "2.0",
        "method": method,
    }

    if params is not None:
        payload["params"] = params

    response = requests.post(snapserver_rpc_url, json=payload)
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise SnapserverError(data["error"])

    return data["result"]


def get_clients(snapserver_rpc_url: str) -> list[dict[str, Any]]:
    """
    Return all connected Snapserver clients.
    """

    result = _rpc_call(
        snapserver_rpc_url,
        "Server.GetStatus",
    )

    clients = []

    for group in result["server"]["groups"]:
        for client in group["clients"]:
            clients.append(client)

    return clients


def set_all_client_volumes(
    snapserver_rpc_url: str,
    percent: int = 100,
    muted: bool = False,
) -> list[dict[str, Any]]:
    """
    Set the volume for all connected clients.
    """

    clients = get_clients(snapserver_rpc_url)

    batch_payload = []

    for i, client in enumerate(clients, start=1):
        batch_payload.append({
            "id": i,
            "jsonrpc": "2.0",
            "method": "Client.SetVolume",
            "params": {
                "id": client["id"],
                "volume": {
                    "percent": percent,
                    "muted": muted,
                },
            },
        })

    response = requests.post(
        snapserver_rpc_url,
        json=batch_payload,
    )
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    SNAPSERVER_RPC_URL = "http://localhost:1780/jsonrpc"
    set_clients_to_max_volume(SNAPSERVER_RPC_URL)
