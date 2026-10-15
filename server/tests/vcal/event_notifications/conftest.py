import pytest

from homeaudio.audio.settings import EventNotificationSettings


@pytest.fixture(autouse=True)
def isolate_event_notification_settings(tmp_path, monkeypatch):
    """Stops EventNotificationSettings() from reading departure_notifications from the real config/ dir."""
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(tmp_path / "notifications.yaml"))
