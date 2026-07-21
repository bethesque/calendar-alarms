import logging
from vcal.snapserver import Snapserver
from vcal.settings import SnapcastSettings

logger = logging.getLogger(__name__)

class SnapserverManager:
    def __init__(self, snapcast_settings: SnapcastSettings, requested_player_names: list[str] | None = None):
        self.snapcast_settings = snapcast_settings
        self.snapserver = Snapserver(snapcast_settings.snapserver_rpc_url)
        self.requested_player_names = requested_player_names

    def connected_player_names(self) -> list[str]:
        if self.requested_player_names:
            return list(set(self.snapserver.connected_client_names()) & set(self.requested_player_names))
        else:
            return self.snapserver.connected_client_names()

    def connected_player_areas(self) -> set[str]:
        return set([sc.area for sc in self.snapcast_settings.snapclients if sc.name in self.connected_player_names() and sc.area and sc.area.strip()])

    def set_volumes(self, usecase: str) -> set[str]:
        try:
            """
            Set the volumes of the Snapcast clients to the appropriate levels for the given usecase.
            If player_names is provided, only those players will be adjusted. Otherwise, all connected players will be adjusted.
            Returns a set of areas containing that were adjusted.
            """
            volumes = self.snapcast_settings.volumes_for_players(self.connected_player_names(), usecase)
            self.snapserver.set_volumes(volumes)
        except Exception:
            logger.exception(f"Error setting snapclients to {usecase} volume - audio may not be heard")

        return self.connected_player_areas()



