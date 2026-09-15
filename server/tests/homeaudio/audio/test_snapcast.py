from homeaudio.audio.settings import SnapcastSettings, SnapclientConfig
from homeaudio.audio.snapcast import SnapserverManager


def _manager(snapclients, connected_client_names, requested_player_names=None):
    settings = SnapcastSettings(snapclients=snapclients)
    manager = SnapserverManager(settings, requested_player_names=requested_player_names)
    manager.snapserver.connected_client_names = lambda: connected_client_names
    return manager


def test_connected_player_names_excludes_disabled_snapclients():
    manager = _manager(
        snapclients=[
            SnapclientConfig(name="kaypi", display_name="KayPi", enabled=True),
            SnapclientConfig(name="patpi", display_name="PatPi", enabled=False),
        ],
        connected_client_names=["kaypi", "patpi"],
    )

    assert manager.connected_player_names() == ["kaypi"]


def test_connected_player_names_excludes_disabled_snapclients_even_when_requested():
    manager = _manager(
        snapclients=[
            SnapclientConfig(name="kaypi", display_name="KayPi", enabled=True),
            SnapclientConfig(name="patpi", display_name="PatPi", enabled=False),
        ],
        connected_client_names=["kaypi", "patpi"],
        requested_player_names=["kaypi", "patpi"],
    )

    assert manager.connected_player_names() == ["kaypi"]


def test_connected_player_names_includes_unconfigured_connected_clients():
    manager = _manager(
        snapclients=[SnapclientConfig(name="kaypi", display_name="KayPi", enabled=False)],
        connected_client_names=["kaypi", "unconfigured-client"],
    )

    assert manager.connected_player_names() == ["unconfigured-client"]
