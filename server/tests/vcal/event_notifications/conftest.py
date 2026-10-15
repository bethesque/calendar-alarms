import pytest

from homeaudio.audio.settings import DepartureNotificationSettings


@pytest.fixture(autouse=True)
def isolate_departure_notification_settings(tmp_path, monkeypatch):
    """Stops DepartureNotificationSettings() from reading departure_time_rules from the real config/ dir."""
    monkeypatch.setitem(DepartureNotificationSettings.model_config, "yaml_file", str(tmp_path / "departure_notifications.yaml"))
