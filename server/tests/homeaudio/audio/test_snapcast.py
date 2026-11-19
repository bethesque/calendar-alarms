from datetime import datetime, time

from homeaudio.audio.settings import Feature, MutePeriod, SnapcastSettings, SnapclientConfig
from homeaudio.audio.snapcast import NullSnapserverManager, PlayerScope, SnapserverManager, snapserver_manager_for_env
from homeaudio.audio.snapserver import Client


def _client(name):
    return Client(id=name, host_name=name, config_name=name, connected=True, last_seen={})


def _manager(snapclients, connected_client_names, scope=PlayerScope.CONNECTED, requested_player_names=None, unmuted_client_names=None, scheduled_muted_player_names=None):
    settings = SnapcastSettings(snapclients=snapclients)
    manager = SnapserverManager(settings, Feature.CALENDAR_ALARMS, scope, requested_player_names=requested_player_names)
    manager.snapserver.connected_clients = lambda: [_client(n) for n in connected_client_names]
    manager.snapserver.get_unmuted_connected_clients = lambda: [_client(n) for n in (unmuted_client_names or [])]
    manager._scheduled_muted_player_names = lambda: set(scheduled_muted_player_names or [])
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


def test_scoped_player_names_excludes_scheduled_muted_players():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi", "patpi"],
        scheduled_muted_player_names=["patpi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_names_excludes_scheduled_muted_players_even_when_requested():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.REQUESTED,
        requested_player_names=["kaypi", "patpi"],
        scheduled_muted_player_names=["patpi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_names_excludes_scheduled_muted_players_with_unmuted_scope():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi", "patpi"],
        scope=PlayerScope.UNMUTED,
        unmuted_client_names=["kaypi", "patpi"],
        scheduled_muted_player_names=["patpi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_names_excludes_both_disabled_and_scheduled_muted_players():
    manager = _manager(
        snapclients=[SnapclientConfig(name="officepi", display_name="OfficePi", enabled=False)],
        connected_client_names=["kaypi", "patpi", "officepi"],
        scheduled_muted_player_names=["patpi"],
    )

    assert manager.scoped_player_names() == ["kaypi"]


def test_scoped_player_names_ignores_scheduled_muted_players_that_are_not_connected():
    manager = _manager(
        snapclients=[],
        connected_client_names=["kaypi"],
        scheduled_muted_player_names=["patpi"],
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

    manager = snapserver_manager_for_env(SnapcastSettings(snapclients=[]), Feature.CALENDAR_ALARMS)

    assert isinstance(manager, SnapserverManager)
    assert manager.scope == PlayerScope.CONNECTED


def test_snapserver_manager_for_env_passes_scope_and_requested_player_names(monkeypatch):
    monkeypatch.setattr("homeaudio.audio.snapcast.SNAPCAST_ENABLED", True)

    manager = snapserver_manager_for_env(SnapcastSettings(snapclients=[]), Feature.CALENDAR_ALARMS, PlayerScope.REQUESTED, ["kaypi"])

    assert isinstance(manager, SnapserverManager)
    assert manager.scope == PlayerScope.REQUESTED
    assert manager.requested_player_names == ["kaypi"]


def test_snapserver_manager_for_env_returns_null_manager_when_snapcast_disabled(monkeypatch):
    monkeypatch.setattr("homeaudio.audio.snapcast.SNAPCAST_ENABLED", False)

    manager = snapserver_manager_for_env(SnapcastSettings(snapclients=[]), Feature.CALENDAR_ALARMS, PlayerScope.UNMUTED)

    assert isinstance(manager, NullSnapserverManager)
    assert manager.scoped_player_names() == []


# 2026-11-16 is a Monday.
MONDAY_10PM = datetime(2026, 11, 16, 22, 0)


def _mute_manager(mute_periods, now, feature=Feature.CALENDAR_ALARMS):
    return SnapserverManager(SnapcastSettings(scheduled_mute_periods=mute_periods), feature, PlayerScope.CONNECTED, now=now)


def _mute_period(snapclients=["kaypi"], days_of_week=[1], allowed_features=[]):
    return MutePeriod(start=time(22, 0), end=time(23, 0), days_of_week=days_of_week, snapclients=snapclients, allowed_features=allowed_features)


def test_scheduled_muted_player_names_includes_snapclients_in_active_period():
    manager = _mute_manager([_mute_period(snapclients=["kaypi", "patpi"])], MONDAY_10PM)

    assert manager._scheduled_muted_player_names() == {"kaypi", "patpi"}


def test_scheduled_muted_player_names_excludes_period_on_other_day():
    manager = _mute_manager([_mute_period(days_of_week=[0, 2])], MONDAY_10PM)

    assert manager._scheduled_muted_player_names() == set()


def test_scheduled_muted_player_names_treats_sunday_as_day_zero():
    manager = _mute_manager([_mute_period(days_of_week=[0])], datetime(2026, 11, 15, 22, 0))

    assert manager._scheduled_muted_player_names() == {"kaypi"}


def test_scheduled_muted_player_names_excludes_period_at_end_time():
    manager = _mute_manager([_mute_period()], datetime(2026, 11, 16, 23, 0))

    assert manager._scheduled_muted_player_names() == set()


def test_scheduled_muted_player_names_excludes_period_before_start_time():
    manager = _mute_manager([_mute_period()], datetime(2026, 11, 16, 21, 59))

    assert manager._scheduled_muted_player_names() == set()


def test_scheduled_muted_player_names_excludes_period_allowing_feature():
    manager = _mute_manager([_mute_period(allowed_features=[Feature.DOORBELL])], MONDAY_10PM, feature=Feature.DOORBELL)

    assert manager._scheduled_muted_player_names() == set()


def test_scheduled_muted_player_names_includes_period_allowing_other_feature():
    manager = _mute_manager([_mute_period(allowed_features=[Feature.DOORBELL])], MONDAY_10PM)

    assert manager._scheduled_muted_player_names() == {"kaypi"}


def test_scheduled_muted_player_names_handles_timezone_aware_now():
    now = datetime(2026, 11, 16, 22, 30).astimezone()
    manager = _mute_manager([_mute_period()], now)

    assert manager._scheduled_muted_player_names() == {"kaypi"}
