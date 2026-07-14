import logging
from vcal.snapserver import Snapserver
from vcal.settings import SnapcastSettings

logger = logging.getLogger(__name__)

class SnapserverManager:
    def __init__(self, snapcast_settings: SnapcastSettings):
        self.snapcast_settings = snapcast_settings
        self.snapserver = Snapserver(snapcast_settings.snapserver_rpc_url())

    def set_volumes(self, usecase: str, player_names: list[str] | None = None) -> set[str]:
        try:
            """
            Set the volumes of the Snapcast clients to the appropriate levels for the given usecase.
            If player_names is provided, only those players will be adjusted. Otherwise, all connected players will be adjusted.
            Returns a set of areas containing that were adjusted.
            """
            player_names = player_names or self.snapserver.connected_client_names()
            self.snapserver.set_volumes(self.snapcast_settings.volumes_for_players(player_names, usecase))
        except Exception:
            logger.exception(f"Error setting snapclients to {usecase} volume - audio may not be heard")

        if player_names:
            # Names were provided or we were able to retrieve the dynamic list from the snapserver
            return set([sc.area for sc in self.snapcast_settings.snapclients if sc.name in player_names and sc.area and sc.area.strip()])
        else:
            # Return all areas
            return set([sc.area for sc in self.snapcast_settings.snapclients if sc.area])



