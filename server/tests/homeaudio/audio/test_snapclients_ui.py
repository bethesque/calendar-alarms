from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from homeaudio.audio.snapclients_ui import SnapclientsRoutes
from homeaudio.audio.snapserver import Client

def make_client():
    app = FastAPI()
    app.include_router(SnapclientsRoutes().router, prefix="/admin")
    return TestClient(app)

def test_snapclients_lists_clients():
    clients = [Client("abc", "kaypi", "Kitchen", True, {"sec": 1790000000, "usec": 0}, latency=42)]
    with patch("homeaudio.audio.snapclients_ui.Snapserver.get_clients", return_value=clients):
        response = make_client().get("/admin/snapclients")

    assert response.status_code == 200
    assert "abc" in response.text
    assert "Kitchen" in response.text
    assert "kaypi" in response.text
    assert "<td>42</td>" in response.text

def test_snapclients_shows_error_when_snapserver_unavailable():
    with patch("homeaudio.audio.snapclients_ui.Snapserver.get_clients", side_effect=RuntimeError("boom")):
        response = make_client().get("/admin/snapclients")

    assert response.status_code == 200
    assert "Could not load snapclients: boom" in response.text

def test_snapclients_has_test_button_using_client_name():
    clients = [Client("abc", "kaypi", "", True, {"sec": 1790000000, "usec": 0})]
    with patch("homeaudio.audio.snapclients_ui.Snapserver.get_clients", return_value=clients):
        response = make_client().get("/admin/snapclients")

    assert 'title="Test" data-name="kaypi"' in response.text

def test_snapclients_ordered_by_name():
    clients = [
        Client("1", "patpi", "", True, {}),
        Client("2", "kaypi", "Kitchen", True, {}),
        Client("3", "officepi", "", True, {}),
    ]
    with patch("homeaudio.audio.snapclients_ui.Snapserver.get_clients", return_value=clients):
        response = make_client().get("/admin/snapclients")

    text = response.text
    assert text.index('data-name="Kitchen"') < text.index('data-name="officepi"') < text.index('data-name="patpi"')
