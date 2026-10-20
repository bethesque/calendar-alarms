from homeaudio.audio.settings import SnapcastSettings, SnapclientConfig
from homeaudio.audio.snapcast import NullSnapserverManager, PlayerScope, SnapserverManager, snapserver_manager_for_env
from homeaudio.audio.snapserver import Client


def _client(name):
    return Client(id=name, host_name=name, config_name=name, connected=True, last_seen={})


def _manager(snapclients, connected_client_names, scope=PlayerScope.CONNECTED, requested_player_names=None, unmuted_client_names=None):
    settings = SnapcastSettings(snapclients=snapclients)
    manager = SnapserverManager(settings, scope, requested_player_names=requested_player_names)
    manager.snapserver.connected_clients = lambda: [_client(n) for n in connected_client_names]
    manager.snapserver.get_unmuted_connected_clients = lambda: [_client(n) for n in (unmuted_client_names or [])]
    return manager


def test_scoped_player_names_excludes_disabled_snapclients():
    manager = _manager(
        snapclients=[
            SnapclientConfig(name="kaypi", display_name="KayPi", enabled=True),
            SnapclientConfig(name="patpi", display_name="PatPi", enabled=False),
        ],
        connected_client_names=["kaypi", "patpi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_names_excludes_disabled_snapclients_even_when_requested():
    manager = _manager(
        snapclients=[
            SnapclientConfig(name="kaypi", display_name="KayPi", enabled=True),
            SnapclientConfig(name="patpi", display_name="PatPi", enabled=False),
        ],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.REQUESTED,
        requested_player_names=["kaypi", "patpi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_names_includes_unconfigured_connected_clients():
    manager = _manager(
        snapclients=[SnapclientConfig(name="kaypi", display_name="KayPi", enabled=False)],
        connected_client_names=["kaypi", "unconfigured-client"],
    )

    assert manager.scoped_player_names() == ["unconfigured-client"]


def test_scoped_player_names_with_connected_scope_ignores_requested_player_names():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.CONNECTED,
        requested_player_names=["kaypi"],
    )

    assert sorted(manager.scoped_player_names()) == ["kaypi", "patpi"]


def test_scoped_player_names_with_requested_scope_returns_requested_connected_players():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.REQUESTED,
        requested_player_names=["kaypi", "officepi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_names_with_requested_scope_falls_back_to_all_connected_when_none_match():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.REQUESTED,
        requested_player_names=["officepi"],
    )

    assert sorted(manager.scoped_player_names()) == ["kaypi", "patpi"]


def test_scoped_player_names_with_requested_scope_and_no_requested_players_returns_all_connected():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.REQUESTED,
    )

    assert sorted(manager.scoped_player_names()) == ["kaypi", "patpi"]


def test_scoped_player_names_with_unmuted_scope_returns_unmuted_players():
    manager = _manager(
        snapclients=[
            SnapclientConfig(name="kaypi", display_name="KayPi", enabled=True),
            SnapclientConfig(name="officepi", display_name="OfficePi", enabled=False),
        ],
        connected_client_names=["kaypi", "patpi", "officepi"],
        scope=PlayerScope.UNMUTED,
        unmuted_client_names=["kaypi", "officepi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_areas_returns_areas_of_scoped_players():
    manager = _manager(
        snapclients=[
            SnapclientConfig(name="kaypi", display_name="KayPi", area="kitchen"),
            SnapclientConfig(name="patpi", display_name="PatPi", area="bedroom"),
        ],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.UNMUTED,
        unmuted_client_names=["kaypi"],
    )

    assert manager.scoped_player_areas() == {"kitchen"}


def test_snapserver_manager_for_env_defaults_to_connected_scope(monkeypatch):
    monkeypatch.setattr("homeaudio.audio.snapcast.SNAPCAST_ENABLED", True)

    manager = snapserver_manager_for_env(SnapcastSettings(snapclients=[]))

    assert isinstance(manager, SnapserverManager)
    assert manager.scope == PlayerScope.CONNECTED


def test_snapserver_manager_for_env_passes_scope_and_requested_player_names(monkeypatch):
    monkeypatch.setattr("homeaudio.audio.snapcast.SNAPCAST_ENABLED", True)

    manager = snapserver_manager_for_env(SnapcastSettings(snapclients=[]), PlayerScope.REQUESTED, ["kaypi"])

    assert isinstance(manager, SnapserverManager)
    assert manager.scope == PlayerScope.REQUESTED
    assert manager.requested_player_names == ["kaypi"]


def test_snapserver_manager_for_env_returns_null_manager_when_snapcast_disabled(monkeypatch):
    monkeypatch.setattr("homeaudio.audio.snapcast.SNAPCAST_ENABLED", False)

    manager = snapserver_manager_for_env(SnapcastSettings(snapclients=[]), PlayerScope.UNMUTED)

    assert isinstance(manager, NullSnapserverManager)
    assert manager.scoped_player_names() == []
