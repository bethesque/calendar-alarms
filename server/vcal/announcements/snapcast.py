from vcal.snapserver import Snapserver
from vcal.settings import SnapcastSettings

class SnapserverManager:
    def __init__(self, snapcast_settings: SnapcastSettings):
        self.snapcast_settings = snapcast_settings
        self.snapserver = Snapserver(snapcast_settings.snapserver_rpc_url())

    def set_volumes(self, usecase: str, player_names: list[str] | None = None) -> set[str]:
        """
        Set the volumes of the Snapcast clients to the appropriate levels for the given usecase.
        If player_names is provided, only those players will be adjusted. Otherwise, all connected players will be adjusted.
        Returns a set of areas containing that were adjusted.
        """
        player_names = player_names or self.snapserver.connected_client_names()
        self.snapserver.set_volumes(self.snapcast_settings.volumes_for_players(player_names, usecase))
        return set([sc.area for sc in self.snapcast_settings.snapclients if sc.name in player_names and sc.area and sc.area.strip()])

