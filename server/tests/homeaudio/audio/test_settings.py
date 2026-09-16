import pytest
import yaml
from pydantic import ValidationError

from homeaudio.audio.settings import EventNotificationSettings, NotificationRule, SnapcastSettings, SnapclientConfig, DepartureNotificationSettings


def test_label_uses_summary_pattern_only():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=75)

    assert rule.label == "gym @ 75 minutes before"


def test_label_joins_multiple_patterns_with_slash():
    rule = NotificationRule(
        summary_pattern="gym",
        description_pattern="strength",
        location_pattern="Croydon",
        offset_minutes=75,
    )

    assert rule.label == "gym/strength/Croydon @ 75 minutes before"


def test_label_falls_back_to_calendar_id_when_no_patterns_set():
    rule = NotificationRule(calendar_id="beth-calendar", offset_minutes=20)

    assert rule.label == "beth-calendar @ 20 minutes before"


def test_label_reflects_zero_offset():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=0)

    assert rule.label == "gym @ 0 minutes before"


def test_label_is_included_in_model_dump():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=75)

    assert rule.model_dump()["label"] == "gym @ 75 minutes before"


def test_label_is_included_in_standard_model_dump_when_nested():
    settings = EventNotificationSettings(
        notification_rules=[NotificationRule(summary_pattern="gym", offset_minutes=75)]
    )

    saved_rule = settings.model_dump()["notification_rules"][0]

    assert saved_rule["label"] == "gym @ 75 minutes before"


def test_label_is_excluded_when_saving_to_file(tmp_path, monkeypatch):
    yaml_file = tmp_path / "notifications.yaml"
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(yaml_file))

    settings = EventNotificationSettings(
        notification_rules=[NotificationRule(summary_pattern="gym", offset_minutes=75)]
    )
    settings.save()

    saved_rule = yaml.safe_load(yaml_file.read_text())["notification_rules"][0]

    assert "label" not in saved_rule
    assert saved_rule["summary_pattern"] == "gym"


def test_notification_rule_is_enabled_by_default():
    rule = NotificationRule(summary_pattern="gym")

    assert rule.enabled is True


def test_enabled_notification_rules_excludes_disabled_rules():
    enabled_rule = NotificationRule(summary_pattern="gym", enabled=True)
    disabled_rule = NotificationRule(summary_pattern="swim", enabled=False)
    settings = EventNotificationSettings(notification_rules=[enabled_rule, disabled_rule])

    assert settings.enabled_notification_rules() == [enabled_rule]


def test_snapclient_config_is_enabled_by_default():
    snapclient = SnapclientConfig(name="kaypi", display_name="KayPi")

    assert snapclient.enabled is True


def test_disabled_snapclient_names_returns_only_disabled_clients():
    enabled_client = SnapclientConfig(name="kaypi", display_name="KayPi", enabled=True)
    disabled_client = SnapclientConfig(name="patpi", display_name="PatPi", enabled=False)
    settings = SnapcastSettings(snapclients=[enabled_client, disabled_client])

    assert settings.disabled_snapclient_names == {"patpi"}


def test_departure_notification_settings_defaults(tmp_path, monkeypatch):
    monkeypatch.setitem(DepartureNotificationSettings.model_config, "yaml_file", str(tmp_path / "departure_notifications.yaml"))

    settings = DepartureNotificationSettings()

    assert settings.enabled is False
    assert settings.api_key == ""
    assert settings.origin_address == ""
    assert settings.parking_minutes == 5
    assert settings.house_to_car_minutes == 5
    assert settings.safety_factor == 10
    assert settings.heads_up_reminder_lead_time == 10
    assert settings.recompute_interval_minutes == 20


def test_departure_notification_settings_saves_and_reloads_from_yaml(tmp_path, monkeypatch):
    yaml_file = tmp_path / "departure_notifications.yaml"
    monkeypatch.setitem(DepartureNotificationSettings.model_config, "yaml_file", str(yaml_file))

    settings = DepartureNotificationSettings(api_key="secret-key", origin_address="1 Home St", safety_factor=25)
    settings.save()

    saved = yaml.safe_load(yaml_file.read_text())
    assert saved["api_key"] == "secret-key"
    assert saved["origin_address"] == "1 Home St"
    assert saved["safety_factor"] == 25

    reloaded = DepartureNotificationSettings()
    assert reloaded.api_key == "secret-key"
    assert reloaded.safety_factor == 25


def test_departure_notification_settings_allows_disabled_with_no_api_key_or_origin_address():
    settings = DepartureNotificationSettings(enabled=False)

    assert settings.enabled is False


def test_departure_notification_settings_rejects_enabled_with_no_api_key():
    with pytest.raises(ValidationError):
        DepartureNotificationSettings(enabled=True, api_key="", origin_address="1 Home St")


def test_departure_notification_settings_rejects_enabled_with_no_origin_address():
    with pytest.raises(ValidationError):
        DepartureNotificationSettings(enabled=True, api_key="secret-key", origin_address="")


def test_departure_notification_settings_allows_enabled_with_api_key_and_origin_address():
    settings = DepartureNotificationSettings(enabled=True, api_key="secret-key", origin_address="1 Home St")

    assert settings.enabled is True
