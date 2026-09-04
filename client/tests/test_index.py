import threading

import pytest
from fastapi.testclient import TestClient

import index


def _audio_config(**overrides):
    return {
        "snapserver_url": "http://snapserver.local:1780/jsonrpc",
        "home_assistant_url": "http://ha.local:8123",
        "home_assistant_player_entity": "living_room",
        "hostname": "patpi",
        **overrides,
    }


class _StubVolumeController:
    def __init__(self):
        self.mute_called = False
        self.unmute_called = False

    def mute(self):
        self.mute_called = True

    def unmute_slowly(self):
        self.unmute_called = True


class _FakeResponse:
    def __init__(self, ok=True, status_code=200, text=""):
        self.ok = ok
        self.status_code = status_code
        self.text = text


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_config_app_config_maps_fields():
    config = index.Config(
        snapserver_rpc_url="http://snap:1780/jsonrpc",
        home_assistant_url="http://ha:8123",
        home_assistant_player_entity="living_room",
        hostname="patpi",
    )

    assert config.app_config == {
        "snapserver_url": "http://snap:1780/jsonrpc",
        "home_assistant_url": "http://ha:8123",
        "home_assistant_player_entity": "living_room",
        "hostname": "patpi",
    }


def test_config_uvicorn_kwargs():
    config = index.Config(
        port=9000,
        host="127.0.0.1",
        log_level="debug",
        snapserver_rpc_url=None,
        home_assistant_url=None,
        home_assistant_player_entity=None,
    )

    assert config.uvicorn_kwargs == {"port": 9000, "host": "127.0.0.1", "log_level": "debug"}


# ---------------------------------------------------------------------------
# toggle() / stop()
# ---------------------------------------------------------------------------

def test_toggle_mutes_snapclient_when_it_is_playing(monkeypatch):
    audio_config = _audio_config()
    monkeypatch.setattr(index, "VolumeController", _StubVolumeController)
    monkeypatch.setattr(index, "_is_snapclient_playing", lambda cfg: (True, "client-1"))

    calls = []
    monkeypatch.setattr(index, "_mute_snapclient", lambda cfg, client_id: calls.append((cfg, client_id)))
    monkeypatch.setattr(index, "_toggle_music_assistant_player", lambda cfg: pytest.fail("should not be called"))

    index.toggle(audio_config)

    # Regression check for the bug where toggle() passed audio_config["snapserver_url"]
    # (a bare string) instead of the whole audio_config dict that _mute_snapclient expects.
    assert calls == [(audio_config, "client-1")]


def test_toggle_toggles_music_assistant_when_snapclient_not_playing(monkeypatch):
    audio_config = _audio_config()
    monkeypatch.setattr(index, "VolumeController", _StubVolumeController)
    monkeypatch.setattr(index, "_is_snapclient_playing", lambda cfg: (False, None))

    calls = []
    monkeypatch.setattr(index, "_mute_snapclient", lambda cfg, client_id: pytest.fail("should not be called"))
    monkeypatch.setattr(index, "_toggle_music_assistant_player", lambda cfg: calls.append(cfg))

    index.toggle(audio_config)

    assert calls == [audio_config]


def test_toggle_end_to_end_calls_mute_client_with_the_url_string_when_playing(monkeypatch):
    # Exercises toggle() -> _mute_snapclient() -> mute_client() without mocking the
    # middle step, so a type mismatch between them would surface here too.
    audio_config = _audio_config()
    monkeypatch.setattr(index, "VolumeController", _StubVolumeController)
    monkeypatch.setattr(index, "_is_snapclient_playing", lambda cfg: (True, "client-9"))

    calls = []
    monkeypatch.setattr(index, "mute_client", lambda url, client_id: calls.append((url, client_id)))

    index.toggle(audio_config)

    assert calls == [(audio_config["snapserver_url"], "client-9")]


def test_toggle_reports_battery_level_when_params_given(monkeypatch):
    audio_config = _audio_config()
    monkeypatch.setattr(index, "VolumeController", _StubVolumeController)
    monkeypatch.setattr(index, "_is_snapclient_playing", lambda cfg: (False, None))
    monkeypatch.setattr(index, "_toggle_music_assistant_player", lambda cfg: None)

    calls = []
    monkeypatch.setattr(index, "_report_battery_level", lambda cfg, params: calls.append((cfg, params)))

    index.toggle(audio_config, {"button_battery_level": "80"})

    assert calls == [(audio_config, {"button_battery_level": "80"})]


def test_toggle_skips_battery_report_when_no_params(monkeypatch):
    audio_config = _audio_config()
    monkeypatch.setattr(index, "VolumeController", _StubVolumeController)
    monkeypatch.setattr(index, "_is_snapclient_playing", lambda cfg: (False, None))
    monkeypatch.setattr(index, "_toggle_music_assistant_player", lambda cfg: None)
    monkeypatch.setattr(index, "_report_battery_level", lambda cfg, params: pytest.fail("should not be called"))

    index.toggle(audio_config)  # no params


def test_stop_mutes_snapclient_and_pauses_music_assistant_regardless_of_playing_state(monkeypatch):
    audio_config = _audio_config()
    monkeypatch.setattr(index, "VolumeController", _StubVolumeController)
    monkeypatch.setattr(index, "get_playing_status", lambda url, hostname: (False, "client-3"))

    mute_calls = []
    pause_calls = []
    battery_calls = []
    monkeypatch.setattr(index, "_mute_snapclient", lambda cfg, client_id: mute_calls.append((cfg, client_id)))
    monkeypatch.setattr(index, "_pause_music_assistant_player", lambda cfg: pause_calls.append(cfg))
    monkeypatch.setattr(index, "_report_battery_level", lambda cfg, params: battery_calls.append((cfg, params)))

    index.stop(audio_config, {"button_battery_level": "50"})

    assert mute_calls == [(audio_config, "client-3")]
    assert pause_calls == [audio_config]
    assert battery_calls == [(audio_config, {"button_battery_level": "50"})]


# ---------------------------------------------------------------------------
# _is_snapclient_playing
# ---------------------------------------------------------------------------

def test_is_snapclient_playing_returns_status_and_client_id(monkeypatch):
    monkeypatch.setattr(index, "get_playing_status", lambda url, hostname: (True, "client-7"))

    is_playing, client_id = index._is_snapclient_playing(_audio_config())

    assert is_playing is True
    assert client_id == "client-7"


def test_is_snapclient_playing_returns_false_none_on_error(monkeypatch):
    def boom(url, hostname):
        raise ValueError("not found")

    monkeypatch.setattr(index, "get_playing_status", boom)

    is_playing, client_id = index._is_snapclient_playing(_audio_config())

    assert is_playing is False
    assert client_id is None


# ---------------------------------------------------------------------------
# _mute_snapclient
# ---------------------------------------------------------------------------

def test_mute_snapclient_extracts_url_from_the_full_audio_config(monkeypatch):
    audio_config = _audio_config()
    calls = []
    monkeypatch.setattr(index, "mute_client", lambda url, client_id: calls.append((url, client_id)))

    index._mute_snapclient(audio_config, "client-42")

    assert calls == [(audio_config["snapserver_url"], "client-42")]


def test_mute_snapclient_swallows_exceptions(monkeypatch):
    def boom(url, client_id):
        raise RuntimeError("network error")

    monkeypatch.setattr(index, "mute_client", boom)

    index._mute_snapclient(_audio_config(), "client-42")  # must not raise


# ---------------------------------------------------------------------------
# _toggle_music_assistant_player / _pause_music_assistant_player
# ---------------------------------------------------------------------------

def test_toggle_music_assistant_player_calls_toggle_pause_play(monkeypatch):
    audio_config = _audio_config()
    calls = []
    monkeypatch.setattr(index, "toggle_pause_play", lambda url, player: calls.append((url, player)))

    index._toggle_music_assistant_player(audio_config)

    assert calls == [(audio_config["home_assistant_url"], audio_config["home_assistant_player_entity"])]


def test_toggle_music_assistant_player_swallows_exceptions(monkeypatch):
    def boom(url, player):
        raise RuntimeError("boom")

    monkeypatch.setattr(index, "toggle_pause_play", boom)

    index._toggle_music_assistant_player(_audio_config())  # must not raise


def test_pause_music_assistant_player_calls_pause_player(monkeypatch):
    audio_config = _audio_config()
    calls = []
    monkeypatch.setattr(index, "pause_player", lambda url, player: calls.append((url, player)))

    index._pause_music_assistant_player(audio_config)

    assert calls == [(audio_config["home_assistant_url"], audio_config["home_assistant_player_entity"])]


def test_pause_music_assistant_player_swallows_exceptions(monkeypatch):
    def boom(url, player):
        raise RuntimeError("boom")

    monkeypatch.setattr(index, "pause_player", boom)

    index._pause_music_assistant_player(_audio_config())  # must not raise


# ---------------------------------------------------------------------------
# _report_battery_level
# ---------------------------------------------------------------------------

def test_report_battery_level_posts_valid_level_to_home_assistant(monkeypatch):
    audio_config = _audio_config()
    calls = []
    monkeypatch.setattr(
        index.requests,
        "post",
        lambda url, json, timeout: calls.append((url, json, timeout)) or _FakeResponse(),
    )

    index._report_battery_level(audio_config, {"button_battery_level": "87"})

    assert len(calls) == 1
    url, payload, timeout = calls[0]
    assert url == f"{audio_config['home_assistant_url']}/api/webhook/{audio_config['hostname']}-flic-button-battery-level"
    assert payload == {"value": 87.0}


def test_report_battery_level_skips_when_battery_level_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(index.requests, "post", lambda *a, **k: calls.append(1))

    index._report_battery_level(_audio_config(), {"button_battery_level": None})

    assert calls == []


def test_report_battery_level_skips_when_battery_level_not_a_number(monkeypatch):
    calls = []
    monkeypatch.setattr(index.requests, "post", lambda *a, **k: calls.append(1))

    index._report_battery_level(_audio_config(), {"button_battery_level": "not-a-number"})

    assert calls == []


def test_report_battery_level_swallows_non_ok_response(monkeypatch):
    monkeypatch.setattr(index.requests, "post", lambda *a, **k: _FakeResponse(ok=False, status_code=500, text="error"))

    index._report_battery_level(_audio_config(), {"button_battery_level": "50"})  # must not raise


def test_report_battery_level_swallows_request_exceptions(monkeypatch):
    def boom(*a, **k):
        raise index.requests.RequestException("network error")

    monkeypatch.setattr(index.requests, "post", boom)

    index._report_battery_level(_audio_config(), {"button_battery_level": "50"})  # must not raise


# ---------------------------------------------------------------------------
# _get_status_body
# ---------------------------------------------------------------------------

def test_get_status_body_builds_expected_dict(monkeypatch):
    audio_config = _audio_config()

    def fake_run(command, capture_output, text):
        outputs = {
            ("amixer",): "Simple mixer control 'Speaker',0\n  Front Left: Playback 80 [80%] [on]\n",
            ("systemctl", "--user", "is-active", "calendar-alarms-snapclient.service"): "active\n",
            ("systemctl", "--user", "is-active", "sendspin-armv6.service"): "inactive\n",
        }
        return type("Result", (), {"stdout": outputs[tuple(command)]})()

    monkeypatch.setattr(index.subprocess, "run", fake_run)
    monkeypatch.setattr(index, "get_client_status", lambda url, hostname: {"connected": True})

    body = index._get_status_body(audio_config)

    assert body["amixer"]["volume"] == "80 (80%)"
    assert body["calendar-alarms-snapclient.service"]["status"] == "active"
    assert body["sendspin-armv6.service"]["status"] == "inactive"
    assert body["calendar-alarms-snapclient-status"] == {"connected": True}


def test_get_status_body_handles_unparseable_amixer_output(monkeypatch):
    audio_config = _audio_config()

    def fake_run(command, capture_output, text):
        if tuple(command) == ("amixer",):
            return type("Result", (), {"stdout": "nonsense output"})()
        return type("Result", (), {"stdout": "active\n"})()

    monkeypatch.setattr(index.subprocess, "run", fake_run)
    monkeypatch.setattr(index, "get_client_status", lambda url, hostname: {})

    body = index._get_status_body(audio_config)

    assert body["amixer"]["volume"] is None


# ---------------------------------------------------------------------------
# muted_alsa
# ---------------------------------------------------------------------------

def test_muted_alsa_mutes_then_unmutes_around_the_block(monkeypatch):
    controller = _StubVolumeController()
    monkeypatch.setattr(index, "VolumeController", lambda: controller)

    entered = []
    with index.muted_alsa():
        entered.append("inside")

    assert entered == ["inside"]
    assert controller.mute_called is True
    assert controller.unmute_called is True


def test_muted_alsa_skips_unmute_when_mute_itself_failed(monkeypatch):
    class _FailingController:
        def mute(self):
            raise RuntimeError("amixer not available")

        def unmute_slowly(self):
            pytest.fail("should not be called since mute failed")

    monkeypatch.setattr(index, "VolumeController", _FailingController)

    with index.muted_alsa():
        pass  # must not raise


def test_muted_alsa_swallows_unmute_errors(monkeypatch):
    class _Controller:
        def mute(self):
            pass

        def unmute_slowly(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(index, "VolumeController", _Controller)

    with index.muted_alsa():
        pass  # must not raise


# ---------------------------------------------------------------------------
# run_in_background
# ---------------------------------------------------------------------------

def test_run_in_background_invokes_target_with_audio_config_and_params():
    calls = []
    done = threading.Event()

    def target(audio_config, params):
        calls.append((audio_config, params))
        done.set()

    index.run_in_background(target, {"a": 1}, {"b": 2})

    assert done.wait(timeout=1)
    assert calls == [({"a": 1}, {"b": 2})]


# ---------------------------------------------------------------------------
# AudioServer (HTTP layer)
# ---------------------------------------------------------------------------

def _server():
    return index.AudioServer(_audio_config())


def test_status_endpoint_returns_status_body(monkeypatch):
    monkeypatch.setattr(index, "_get_status_body", lambda cfg: {"ok": True})
    client = TestClient(_server().app)

    response = client.get("/audio/status")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_status_endpoint_returns_500_on_error(monkeypatch):
    def boom(cfg):
        raise RuntimeError("boom")

    monkeypatch.setattr(index, "_get_status_body", boom)
    client = TestClient(_server().app)

    response = client.get("/audio/status")

    assert response.status_code == 500
    assert response.text == "error"


def test_audio_toggle_endpoint_starts_toggle_and_returns_202(monkeypatch):
    server = _server()
    done = threading.Event()
    calls = []

    def fake_toggle(audio_config, params):
        calls.append((audio_config, params))
        done.set()

    monkeypatch.setattr(index, "toggle", fake_toggle)
    client = TestClient(server.app)

    response = client.post("/audio/toggle", headers={"button-battery-level": "42"})

    assert response.status_code == 202
    assert response.text == "Toggling audio\n"
    assert done.wait(timeout=1)
    assert calls == [(server.audio_config, {"button_battery_level": "42"})]


def test_audio_toggle_endpoint_returns_409_when_busy():
    server = _server()
    server._operation_lock.acquire()
    try:
        client = TestClient(server.app)
        response = client.post("/audio/toggle")

        assert response.status_code == 409
        assert "Busy" in response.text
    finally:
        server._operation_lock.release()


def test_audio_stop_endpoint_starts_stop_and_returns_202(monkeypatch):
    server = _server()
    done = threading.Event()
    calls = []

    def fake_stop(audio_config, params):
        calls.append((audio_config, params))
        done.set()

    monkeypatch.setattr(index, "stop", fake_stop)
    client = TestClient(server.app)

    response = client.post("/audio/stop")

    assert response.status_code == 202
    assert response.text == "Stopping audio\n"
    assert done.wait(timeout=1)
    assert calls == [(server.audio_config, {"button_battery_level": None})]


def test_audio_stop_endpoint_returns_409_when_busy():
    server = _server()
    server._operation_lock.acquire()
    try:
        client = TestClient(server.app)
        response = client.post("/audio/stop")

        assert response.status_code == 409
        assert "Busy" in response.text
    finally:
        server._operation_lock.release()
