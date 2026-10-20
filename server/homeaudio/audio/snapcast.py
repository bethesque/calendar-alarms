import logging
from typing import Protocol
from homeaudio.audio.snapserver import Snapserver
from homeaudio.audio.settings import SnapcastSettings
from homeaudio.env import SNAPCAST_ENABLED
from enum import Enum

logger = logging.getLogger(__name__)

class SnapserverManagerProtocol(Protocol):
    def scoped_player_names(self) -> list[str]:
        ...

    def scoped_player_areas(self) -> set[str]:
        ...

    def set_volumes(self, usecase: str) -> set[str]:
        ...


class NullSnapserverManager:
    def scoped_player_names(self) -> list[str]:
        return []

    def scoped_player_areas(self) -> set[str]:
        return set()

    def set_volumes(self, usecase: str) -> set[str]:
        ...

class PlayerScope(Enum):
    CONNECTED = "CONNECTED"
    UNMUTED = "UNMUTED"
    REQUESTED = "REQUESTED"


class SnapserverManager:
    def __init__(self, snapcast_settings: SnapcastSettings, scope: PlayerScope, requested_player_names: list[str] | None = None):
        self.snapcast_settings = snapcast_settings
        self.snapserver = Snapserver(snapcast_settings.snapserver_rpc_url)
        self.scope = scope
        self.requested_player_names = requested_player_names
        self._scoped_player_names: list[str] | None = None

    def scoped_player_names(self) -> list[str]:
        if self._scoped_player_names is None:

            if self.scope == PlayerScope.REQUESTED and self.requested_player_names:
                connected_clients = self.snapserver.connected_clients()
                connected_client_names = [c.name for c in connected_clients]
                names = set(connected_client_names) & set(self.requested_player_names)
                # If the requested players don't match any clients, return them all rather than not play
                # over any players
                if not names:
                    logger.info(f"The requested players {self.requested_player_names} are not available. Using all players.")
                    names = set(connected_client_names)
            elif self.scope == PlayerScope.UNMUTED:
                names = set([c.name for c in self.snapserver.get_unmuted_connected_clients()])
            else:
                names = set([c.name for c in self.snapserver.connected_clients()])

            self._scoped_player_names = list(names - self.snapcast_settings.disabled_snapclient_names)

        return self._scoped_player_names

    def scoped_player_areas(self) -> set[str]:
        conn_player_names = self.scoped_player_names()
        return set([sc.area for sc in self.snapcast_settings.snapclients if sc.name in conn_player_names and sc.area and sc.area.strip()])

    def set_volumes(self, usecase: str) -> set[str]:
        try:
            """
            Set the volumes of the Snapcast clients to the appropriate levels for the given usecase.
            If player_names is provided, only those players will be adjusted. Otherwise, all connected players will be adjusted.
            Returns a set of areas containing that were adjusted.
            """
            volumes = self.snapcast_settings.volumes_for_players(self.scoped_player_names(), usecase)
            self.snapserver.set_volumes(volumes)
        except Exception:
            logger.exception(f"Error setting snapclients to {usecase} volume - audio may not be heard")

        return self.scoped_player_areas()

def snapserver_manager_for_env(snapcast_settings: SnapcastSettings, scope: PlayerScope = PlayerScope.CONNECTED, requested_player_names: list[str] | None = None) -> SnapserverManagerProtocol:
    return SnapserverManager(snapcast_settings, scope, requested_player_names) if SNAPCAST_ENABLED else NullSnapserverManager()
