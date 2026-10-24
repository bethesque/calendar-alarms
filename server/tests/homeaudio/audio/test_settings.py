from datetime import time

import pytest
import yaml
from pydantic import ValidationError

from homeaudio.audio.settings import EventNotificationSettings, TimeRange, NotificationRule, NotificationTiming, SnapcastSettings, SnapclientConfig, PlayerGroup, DepartureTimeRule, LocationBasedDepartureTimes, UploadedFile, GoogleCalendarSettings, AvailableGoogleCalendars, GoogleCalendar


def test_label_uses_summary_pattern_only():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=75)

    assert rule.label == "When 'gym' then announce 75 minutes before event start time"


def test_label_joins_multiple_patterns_with_slash():
    rule = NotificationRule(
        summary_pattern="gym",
        description_pattern="strength",
        location_pattern="Croydon",
        offset_minutes=75,
    )

    assert rule.label == "When 'gym/strength/Croydon' then announce 75 minutes before event start time"


def test_label_falls_back_to_calendar_id_when_no_patterns_set():
    rule = NotificationRule(calendar_id="beth-calendar", offset_minutes=20)

    assert rule.label == "When 'beth-calendar' then announce 20 minutes before event start time"


def test_label_uses_calendar_name_from_available_calendars(tmp_path, monkeypatch):
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(tmp_path / "notifications.yaml"))
    monkeypatch.setitem(AvailableGoogleCalendars.model_config, "yaml_file", str(tmp_path / "available_google_calendars.yaml"))
    AvailableGoogleCalendars(calendars=[GoogleCalendar(id="beth-calendar", name="Beth")]).save()

    settings = EventNotificationSettings(
        notification_rules=[NotificationRule(calendar_id="beth-calendar", offset_minutes=20)]
    )

    assert settings.notification_rules[0].label == "When 'Beth' then announce 20 minutes before event start time"


def test_label_falls_back_to_calendar_id_when_calendar_not_available(tmp_path, monkeypatch):
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(tmp_path / "notifications.yaml"))
    monkeypatch.setitem(AvailableGoogleCalendars.model_config, "yaml_file", str(tmp_path / "available_google_calendars.yaml"))

    settings = EventNotificationSettings(
        notification_rules=[NotificationRule(calendar_id="beth-calendar", offset_minutes=20)]
    )

    assert settings.notification_rules[0].label == "When 'beth-calendar' then announce 20 minutes before event start time"


def test_label_reflects_zero_offset():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=0)

    assert rule.label == "When 'gym' then announce 0 minutes before event start time"


def test_departure_notification_rule_label_counts_down_to_departure():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=10, notification_timing=NotificationTiming.DEPARTURE_TIME)

    assert rule.label == "When 'gym' then announce 10 minutes before departure time"


def test_label_includes_notification_type():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=10, notification_type="alarm")

    assert rule.label == "When 'gym' then alarm 10 minutes before event start time"


def test_label_is_included_in_model_dump():
    rule = NotificationRule(summary_pattern="gym", offset_minutes=75)

    assert rule.model_dump()["label"] == "When 'gym' then announce 75 minutes before event start time"


def test_label_is_included_in_standard_model_dump_when_nested():
    settings = EventNotificationSettings(
        notification_rules=[NotificationRule(summary_pattern="gym", offset_minutes=75)]
    )

    saved_rule = settings.model_dump()["notification_rules"][0]

    assert saved_rule["label"] == "When 'gym' then announce 75 minutes before event start time"


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


def test_household_names_are_sorted_ignoring_case():
    settings = EventNotificationSettings(household_names=["dwain", "Beth", "alex", "Cam"])

    assert settings.household_names == ["alex", "Beth", "Cam", "dwain"]


def test_household_names_are_sorted_ignoring_case_when_saving_to_file(tmp_path, monkeypatch):
    yaml_file = tmp_path / "notifications.yaml"
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(yaml_file))

    EventNotificationSettings(household_names=["dwain", "Beth", "alex", "Cam"]).save()

    assert yaml.safe_load(yaml_file.read_text())["household_names"] == ["alex", "Beth", "Cam", "dwain"]


def test_departure_time_notification_rule_saves_and_reloads_from_yaml(tmp_path, monkeypatch):
    yaml_file = tmp_path / "notifications.yaml"
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(yaml_file))

    EventNotificationSettings(notification_rules=[NotificationRule(summary_pattern="gym", offset_minutes=10, notification_timing=NotificationTiming.DEPARTURE_TIME)]).save()

    saved_rule = yaml.safe_load(yaml_file.read_text())["notification_rules"][0]
    assert saved_rule["notification_timing"] == "departure_time"
    assert "label" not in saved_rule
    assert EventNotificationSettings().notification_rules[0].notification_timing == NotificationTiming.DEPARTURE_TIME


def test_notification_rule_is_enabled_by_default():
    rule = NotificationRule(summary_pattern="gym")

    assert rule.enabled is True


def test_enabled_notification_rules_excludes_disabled_rules():
    enabled_rule = NotificationRule(summary_pattern="gym", enabled=True)
    disabled_rule = NotificationRule(summary_pattern="swim", enabled=False)
    settings = EventNotificationSettings(notification_rules=[enabled_rule, disabled_rule])

    assert settings.enabled_notification_rules() == [enabled_rule]


def test_event_start_notification_rules_returns_enabled_event_start_rules():
    event_start_rule = NotificationRule(summary_pattern="gym")
    departure_time_rule = NotificationRule(summary_pattern="gym", notification_timing=NotificationTiming.DEPARTURE_TIME)
    disabled_rule = NotificationRule(summary_pattern="swim", enabled=False)
    settings = EventNotificationSettings(notification_rules=[event_start_rule, departure_time_rule, disabled_rule])

    assert settings.event_start_notification_rules() == [event_start_rule]


def test_departure_time_notification_rules_returns_enabled_departure_time_rules():
    event_start_rule = NotificationRule(summary_pattern="gym")
    departure_time_rule = NotificationRule(summary_pattern="gym", notification_timing=NotificationTiming.DEPARTURE_TIME)
    disabled_rule = NotificationRule(summary_pattern="swim", notification_timing=NotificationTiming.DEPARTURE_TIME, enabled=False)
    settings = EventNotificationSettings(notification_rules=[event_start_rule, departure_time_rule, disabled_rule])

    assert settings.departure_time_notification_rules() == [departure_time_rule]


def test_snapclient_config_is_enabled_by_default():
    snapclient = SnapclientConfig(name="kaypi", display_name="KayPi")

    assert snapclient.enabled is True


def test_disabled_snapclient_names_returns_only_disabled_clients():
    enabled_client = SnapclientConfig(name="kaypi", display_name="KayPi", enabled=True)
    disabled_client = SnapclientConfig(name="patpi", display_name="PatPi", enabled=False)
    settings = SnapcastSettings(snapclients=[enabled_client, disabled_client])

    assert settings.disabled_snapclient_names == {"patpi"}


def test_snapcast_settings_rejects_player_group_with_same_name_as_snapclient():
    with pytest.raises(ValidationError, match="kaypi"):
        SnapcastSettings(
            snapclients=[SnapclientConfig(name="kaypi", display_name="KayPi")],
            player_groups=[PlayerGroup(name="kaypi", player_names=["kaypi"])],
        )


def test_snapcast_settings_allows_player_group_with_different_name_to_snapclients():
    settings = SnapcastSettings(
        snapclients=[SnapclientConfig(name="kaypi", display_name="KayPi")],
        player_groups=[PlayerGroup(name="upstairs", player_names=["kaypi"])],
    )

    assert settings.player_groups[0].name == "upstairs"


def test_departure_notification_settings_defaults(tmp_path, monkeypatch):
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(tmp_path / "notifications.yaml"))

    settings = EventNotificationSettings()

    assert settings.location_based_departure_times.enabled is False
    assert settings.location_based_departure_times.api_key == ""
    assert settings.location_based_departure_times.origin_address == ""
    assert settings.location_based_departure_times.parking_minutes == 5
    assert settings.location_based_departure_times.house_to_car_minutes == 5
    assert settings.location_based_departure_times.safety_factor == 10
    assert settings.location_based_departure_times.recompute_interval_minutes == 30
    assert settings.heads_up_reminder_lead_time == 10


def test_departure_notification_settings_saves_and_reloads_from_yaml(tmp_path, monkeypatch):
    yaml_file = tmp_path / "notifications.yaml"
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(yaml_file))

    settings = EventNotificationSettings(location_based_departure_times=LocationBasedDepartureTimes(api_key="secret-key", origin_address="1 Home St", safety_factor=25))
    settings.save()

    saved = yaml.safe_load(yaml_file.read_text())
    assert saved["location_based_departure_times"]["api_key"] == "secret-key"
    assert saved["location_based_departure_times"]["origin_address"] == "1 Home St"
    assert saved["location_based_departure_times"]["safety_factor"] == 25

    reloaded = EventNotificationSettings()
    assert reloaded.location_based_departure_times.api_key == "secret-key"
    assert reloaded.location_based_departure_times.safety_factor == 25


def test_departure_time_rules_save_and_reload_from_yaml(tmp_path, monkeypatch):
    yaml_file = tmp_path / "notifications.yaml"
    monkeypatch.setitem(EventNotificationSettings.model_config, "yaml_file", str(yaml_file))

    EventNotificationSettings(departure_time_rules=[DepartureTimeRule(summary_pattern="Gym", departure_minutes=11)]).save()

    assert yaml.safe_load(yaml_file.read_text())["departure_time_rules"] == [{"summary_pattern": "Gym", "location_pattern": None, "departure_minutes": 11, "override_calculated_departure_time": False}]
    assert EventNotificationSettings().departure_time_rules == [DepartureTimeRule(summary_pattern="Gym", departure_minutes=11)]


def test_departure_time_rule_label_includes_summary_and_location_patterns():
    rule = DepartureTimeRule(summary_pattern="Gym", location_pattern="Croydon", departure_minutes=10)

    assert rule.label == "When 'Gym/Croydon' then depart 10 minutes before event start time"


def test_departure_notification_settings_allows_disabled_with_no_api_key_or_origin_address():
    settings = EventNotificationSettings(location_based_departure_times=LocationBasedDepartureTimes(enabled=False))

    assert settings.location_based_departure_times.enabled is False


def test_departure_notification_settings_rejects_enabled_with_no_api_key():
    with pytest.raises(ValidationError):
        EventNotificationSettings(location_based_departure_times=LocationBasedDepartureTimes(enabled=True, api_key="", origin_address="1 Home St"))


def test_departure_notification_settings_rejects_enabled_with_no_origin_address():
    with pytest.raises(ValidationError):
        EventNotificationSettings(location_based_departure_times=LocationBasedDepartureTimes(enabled=True, api_key="secret-key", origin_address=""))


def test_departure_notification_settings_allows_enabled_with_api_key_and_origin_address():
    settings = EventNotificationSettings(location_based_departure_times=LocationBasedDepartureTimes(enabled=True, api_key="secret-key", origin_address="1 Home St"))

    assert settings.location_based_departure_times.enabled is True


def test_uploaded_file_content_decodes_base64_data_url():
    uploaded = UploadedFile(name="token.json", size=13, type="application/json", data="data:application/json;base64,eyJhIjogImIifQ==")

    assert uploaded.content() == b'{"a": "b"}'


def test_google_calendar_token_info_is_none_without_token_file(tmp_path, monkeypatch):
    monkeypatch.setitem(GoogleCalendarSettings.model_config, "yaml_file", str(tmp_path / "google_calendar.yaml"))

    assert GoogleCalendarSettings().token_info() is None


def test_google_calendar_token_info_parses_token_file_json(tmp_path, monkeypatch):
    monkeypatch.setitem(GoogleCalendarSettings.model_config, "yaml_file", str(tmp_path / "google_calendar.yaml"))
    token_file = UploadedFile(name="token.json", size=13, type="application/json", data="data:application/json;base64,eyJhIjogImIifQ==")

    assert GoogleCalendarSettings(token_file=token_file).token_info() == {"a": "b"}



def test_time_range_allows_end_after_start():
    time_range = TimeRange(start=time(7, 0), end=time(21, 0))

    assert time_range.end == time(21, 0)


def test_time_range_rejects_end_equal_to_start():
    with pytest.raises(ValidationError):
        TimeRange(start=time(7, 0), end=time(7, 0))


def test_time_range_rejects_end_before_start():
    with pytest.raises(ValidationError):
        TimeRange(start=time(21, 0), end=time(7, 0))
