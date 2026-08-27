import yaml

from homeaudio.audio.settings import EventNotificationSettings, NotificationRule


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
