from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
import requests
import logging

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Client:
    id: str
    host_name: str
    config_name: str

    def __str__(self) -> str:
        return f"{self.id}:{self.host_name}"

    @property
    def name(self) -> str:
        return self.config_name or self.host_name



class Snapserver:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._rpc_id = 1
        self._connected_clients = None

    # -------------------------
    # RPC
    # -------------------------
    def _rpc(self, method: str, params: dict | None = None) -> dict:
        payload = {
            "id": self._rpc_id,
            "jsonrpc": "2.0",
            "method": method,
        }

        if params is not None:
            payload["params"] = params

        self._rpc_id += 1

        resp = requests.post(self.base_url, json=payload, timeout=5)
        resp.raise_for_status()

        data = resp.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        return data["result"]

    def _batch_rpc(self, calls: list[dict]) -> list[dict]:
        start_id = self._rpc_id

        for i, call in enumerate(calls):
            call["jsonrpc"] = "2.0"
            call["id"] = start_id + i

        self._rpc_id += len(calls)

        resp = requests.post(self.base_url, json=calls, timeout=5)
        resp.raise_for_status()
        return resp.json()

    # -------------------------
    # Status / clients
    # -------------------------
    def _get_status(self) -> dict:
        return self._rpc("Server.GetStatus")

    def connected_clients(self) -> list[Client]:
        if self._connected_clients is None:
            self._connected_clients = self._get_clients(only_connected=True)

        return self._connected_clients

    def _get_clients(self, only_connected: bool = False) -> list[Client]:
        status = self._get_status()

        clients: list[Client] = []

        for group in status["server"]["groups"]:
            for c in group.get("clients", []):
                if only_connected and c.get("connected") is not True:
                    continue

                clients.append(
                    Client(
                        id=c["id"],
                        host_name=c["host"]["name"],
                        config_name=c["config"]["name"],
                    )
                )

        return clients

    def connected_client_names(self) -> list[str]:
        return [ client.name for client in self.connected_clients() ]

    # def _clients_by_host(
    #     self,
    #     only_connected: bool = True,
    # ) -> dict[str, list[str]]:
    #     """
    #     host -> list of client_ids
    #     """
    #     mapping: dict[str, list[str]] = {}

    #     for client in self._clients(only_connected=only_connected):
    #         mapping.setdefault(client.host, []).append(client.id)

    #     return mapping

    # -------------------------
    # Control
    # -------------------------
    def _set_client(self, client_id: str, percent: int, muted: bool) -> dict:
        return {
            "method": "Client.SetVolume",
            "params": {
                "id": client_id,
                "volume": {
                    "percent": percent,
                    "muted": muted,
                },
            },
        }

    def set_volumes(self, host_volumes: dict) -> None:
        clients = self.connected_clients()
        logger.info(f"Setting clients volumes to {host_volumes} (others are muted)")
        allowed_hosts = host_volumes.keys()

        calls = [
            self._set_client(
                c.id,
                host_volumes.get(c.name, 0),
                c.name not in allowed_hosts,
            )
            for c in clients
        ]

        if calls:
            self._batch_rpc(calls)

    def set_all_connected_full_volume(self) -> None:
        clients = self._get_clients(only_connected=True)
        logger.info(f"Setting clients {', '.join(c.host_name for c in clients)} to full volume")

        calls = [
            self._set_client(c.id, 100, False)
            for c in clients
        ]

        if calls:
            self._batch_rpc(calls)

    def set_connected_full_volume(
        self,
        allowed_client_names: list[str] | None = None,
    ) -> None:
        if not allowed_client_names:
            return self.set_all_connected_full_volume()

        logger.info(f"Setting clients {", ".join(allowed_client_names)} to full volume, others are muted")
        allowed_hosts = set(allowed_client_names)
        clients = self._get_clients(only_connected=True)

        calls = [
            self._set_client(
                c.id,
                100,
                c.host_name not in allowed_hosts,
            )
            for c in clients
        ]

        if calls:
            self._batch_rpc(calls)

    # -------------------------
    # Context manager
    # -------------------------
    @contextmanager
    def only_players(self, *allowed_client_hosts: str):
        allowed_hosts = set(allowed_client_hosts)
        clients = self._get_clients(only_connected=True)

        # ENTER
        enter_calls = [
            self._set_client(
                c.id,
                100,
                c.host_name not in allowed_hosts,
            )
            for c in clients
        ]

        if enter_calls:
            self._batch_rpc(enter_calls)

        try:
            yield
        finally:
            # EXIT: restore all
            exit_calls = [
                self._set_client(c.id, 100, False)
                for c in clients
            ]

            if exit_calls:
                self._batch_rpc(exit_calls)

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
