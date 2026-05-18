# vcal/snapserver.py

from typing import Any
import requests
import logging

logger = logging.getLogger(__name__)

class SnapserverError(Exception):
    pass

def set_clients_to_max_volume(ca_snapserver_rpc_url):
    clients = get_connected_clients(ca_snapserver_rpc_url)

    logger.info(
        "Connected snapclients: %s",
        ", ".join(
            f"{client['host']['name']} ({client['id']})"
            for client in clients
        ),
    )

    results = set_all_client_volumes(
        ca_snapserver_rpc_url,
        percent=100,
    )

    logger.debug("\nVolume update results:")
    for result in results:
        logger.debug(result)

def _rpc_call(
    ca_snapserver_rpc_url: str,
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

    response = requests.post(ca_snapserver_rpc_url, json=payload)
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise SnapserverError(data["error"])

    return data["result"]


def get_connected_clients(ca_snapserver_rpc_url: str) -> list[dict[str, Any]]:
    """
    Return all connected Snapserver clients.
    """

    result = _rpc_call(
        ca_snapserver_rpc_url,
        "Server.GetStatus",
    )

    clients = []

    for group in result["server"]["groups"]:
        for client in group["clients"]:
            if client['connected']:
                clients.append(client)

    return clients


def set_all_client_volumes(
    ca_snapserver_rpc_url: str,
    percent: int = 100,
    muted: bool = False,
) -> list[dict[str, Any]]:
    """
    Set the volume for all connected clients.
    """

    clients = get_connected_clients(ca_snapserver_rpc_url)

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

    logger.info(
        "Setting volume to %d%% and muted to %s for snapclients: %s",
        percent,
        muted,
        ", ".join(
            f"{client['host']['name']} ({client['id']})"
            for client in clients
        ),
    )

    response = requests.post(
        ca_snapserver_rpc_url,
        json=batch_payload,
    )
    response.raise_for_status()

    return response.json()
