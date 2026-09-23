import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from homeaudio.vcal.cal.google_calendar import Event
from homeaudio.vcal.event_notifications.events import EventNotifications, NotificationType
from homeaudio.audio.settings import NotificationRule, DepartureNotificationSettings

TIMEZONE = ZoneInfo("Australia/Melbourne")


def _departure_notification_settings(**overrides) -> DepartureNotificationSettings:
    defaults = dict(house_to_car_minutes=5, heads_up_reminder_lead_time=10)
    defaults.update(overrides)
    return DepartureNotificationSettings(**defaults)


def test_notifications_support_description_rules():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        notification_type="alarm",
        offset_minutes=75,
    )

    notifications = EventNotifications(event).notifications([rule])

    assert len(notifications) == 1
    assert notifications[0].type == NotificationType.ALARM
    assert notifications[0].offset == 75
    assert notifications[0].notification_time == datetime.datetime(2026, 4, 28, 10, 45, tzinfo=TIMEZONE)


def test_notification_rule_rejects_invalid_notification_type():
    with pytest.raises(ValidationError):
        NotificationRule(summary_pattern="gym", notification_type="beep")


def test_notification_rule_rejects_rule_with_no_matcher_set():
    with pytest.raises(ValidationError):
        NotificationRule()


def test_notification_rule_accepts_rule_with_only_summary_pattern_set():
    NotificationRule(summary_pattern="gym")


def test_notification_rule_accepts_rule_with_only_description_pattern_set():
    NotificationRule(description_pattern="strength")


def test_notification_rule_accepts_rule_with_only_location_pattern_set():
    NotificationRule(location_pattern="Croydon")


def test_notification_rule_accepts_rule_with_only_calendar_id_set():
    NotificationRule(calendar_id="beth-calendar")


def test_notification_rule_rejects_rule_with_only_blank_matchers_set():
    with pytest.raises(ValidationError):
        NotificationRule(summary_pattern="", description_pattern="", location_pattern="", calendar_id="")


def test_notifications_deduplicate_matching_tag_and_rule_notifications():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="#alarm20 #alarm20",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        notification_type="alarm",
        offset_minutes=20,
        reminder="Remember to eat."
    )

    notifications = EventNotifications(event).notifications([rule])

    assert len(notifications) == 1
    assert notifications[0].type == NotificationType.ALARM
    assert notifications[0].offset == 20
    assert notifications[0].notification_rule.reminder == "Remember to eat."


def test_notifications_support_address_pattern():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    matching_event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a workout",
        location="Croydon Leisure Centre",
        start_time=start_time,
    )
    non_matching_event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a workout",
        location="Ringwood Leisure Centre",
        start_time=start_time,
    )
    no_location_event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        location_pattern="Croydon",
        notification_type="alarm",
        offset_minutes=75,
    )

    assert len(EventNotifications(matching_event).notifications([rule])) == 1
    assert EventNotifications(non_matching_event).notifications([rule]) == []
    assert EventNotifications(no_location_event).notifications([rule]) == []


def test_notifications_address_pattern_is_case_insensitive():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a workout",
        location="Croydon Leisure Centre",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        location_pattern="croydon",
        notification_type="alarm",
        offset_minutes=75,
    )

    assert len(EventNotifications(event).notifications([rule])) == 1


def test_notifications_support_description_pattern():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    matching_event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a strength workout",
        start_time=start_time,
    )
    non_matching_event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a cardio workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        description_pattern="strength",
        notification_type="alarm",
        offset_minutes=75,
    )

    assert len(EventNotifications(matching_event).notifications([rule])) == 1
    assert EventNotifications(non_matching_event).notifications([rule]) == []


def test_notifications_description_pattern_is_case_insensitive():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a Strength workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        description_pattern="strength",
        notification_type="alarm",
        offset_minutes=75,
    )

    assert len(EventNotifications(event).notifications([rule])) == 1


def test_notifications_empty_description_and_address_patterns_do_not_filter():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a workout",
        location="Croydon Leisure Centre",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        description_pattern="",
        location_pattern="",
        notification_type="alarm",
        offset_minutes=75,
    )

    assert len(EventNotifications(event).notifications([rule])) == 1


def test_notifications_require_pattern_description_pattern_and_address_pattern_to_all_match():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    all_match = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a strength workout",
        location="Croydon Leisure Centre",
        start_time=start_time,
    )
    summary_does_not_match = Event(
        calendar_id="id",
        owner="Beth",
        summary="Swim session",
        description="This is a strength workout",
        location="Croydon Leisure Centre",
        start_time=start_time,
    )
    description_does_not_match = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a cardio workout",
        location="Croydon Leisure Centre",
        start_time=start_time,
    )
    address_does_not_match = Event(
        calendar_id="id",
        owner="Beth",
        summary="Gym session",
        description="This is a strength workout",
        location="Ringwood Leisure Centre",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        description_pattern="strength",
        location_pattern="Croydon",
        notification_type="alarm",
        offset_minutes=75,
    )

    assert len(EventNotifications(all_match).notifications([rule])) == 1
    assert EventNotifications(summary_does_not_match).notifications([rule]) == []
    assert EventNotifications(description_does_not_match).notifications([rule]) == []
    assert EventNotifications(address_does_not_match).notifications([rule]) == []


def test_notifications_require_exact_matching_calendar_id():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    matching_event = Event(
        calendar_id="beth-calendar",
        owner="Beth",
        summary="Gym session",
        description="This is a gym workout",
        start_time=start_time,
    )
    non_matching_event = Event(
        calendar_id="alex-calendar",
        owner="Alex",
        summary="Gym session",
        description="This is a gym workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        notification_type="alarm",
        offset_minutes=75,
        calendar_id="beth-calendar",
    )

    assert len(EventNotifications(matching_event).notifications([rule])) == 1
    assert EventNotifications(non_matching_event).notifications([rule]) == []


def test_notifications_calendar_id_matches_any_rule_when_event_calendar_id_not_specified():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="",
        owner="Beth",
        summary="Gym session",
        description="This is a gym workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        notification_type="alarm",
        offset_minutes=75,
        calendar_id="beth-calendar",
    )

    assert len(EventNotifications(event).notifications([rule])) == 1


def test_notifications_calendar_id_matches_any_event_when_rule_calendar_id_not_specified():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="beth-calendar",
        owner="Beth",
        summary="Gym session",
        description="This is a gym workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        summary_pattern="gym",
        notification_type="alarm",
        offset_minutes=75,
    )

    assert len(EventNotifications(event).notifications([rule])) == 1


def test_departure_notification_rule_matches_against_the_target_event_but_fires_on_the_leave_event():
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    car_departure_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="",
        location="123 Fake St",
        start_time=start_time,
        car_departure_time=car_departure_time,
    )

    rule = NotificationRule(
        summary_pattern="Morning meeting",
        notification_type="announce",
        offset_minutes=15,
        reminder="Grab your coat.",
    )

    notifications = EventNotifications(event).notifications(
        departure_notification_settings=_departure_notification_settings(notification_rules=[rule])
    )

    rule_notifications = [n for n in notifications if n.notification_rule is not None]
    assert len(rule_notifications) == 1
    assert rule_notifications[0].notification_rule.reminder == "Grab your coat."
    # The rule matches on the target event's summary, but the notification fires against the
    # leave-for event, not the target event.
    assert rule_notifications[0].event.summary == "Leave for Morning meeting"
    walk_out_time = datetime.datetime(2026, 4, 28, 11, 55, tzinfo=TIMEZONE)
    assert rule_notifications[0].event.start_time == walk_out_time
    assert rule_notifications[0].notification_time == walk_out_time - datetime.timedelta(minutes=15)


def test_departure_notification_keeps_multiple_matching_rules_at_the_same_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    car_departure_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="",
        location="123 Fake St",
        start_time=start_time,
        car_departure_time=car_departure_time,
    )

    rule_one = NotificationRule(
        summary_pattern="Morning meeting",
        notification_type="announce",
        offset_minutes=15,
        reminder="Grab your coat.",
    )
    rule_two = NotificationRule(
        summary_pattern="Morning meeting",
        notification_type="announce",
        offset_minutes=15,
        reminder="Take an umbrella.",
    )

    notifications = EventNotifications(event).notifications(
        departure_notification_settings=_departure_notification_settings(notification_rules=[rule_one, rule_two])
    )

    rule_notifications = [n for n in notifications if n.notification_rule is not None]

    # Both rules match the same event at the same notification_time - neither is deduplicated away.
    assert len(rule_notifications) == 2
    assert {n.notification_rule.reminder for n in rule_notifications} == {"Grab your coat.", "Take an umbrella."}
    assert rule_notifications[0].notification_time == rule_notifications[1].notification_time


def test_departure_notification_rule_overrides_fixed_announcement_at_the_same_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    car_departure_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="",
        location="123 Fake St",
        start_time=start_time,
        car_departure_time=car_departure_time,
    )

    # offset_minutes matches heads_up_reminder_lead_time, so this rule's notification lands at the
    # same notification_time as the fixed heads-up announcement.
    rule = NotificationRule(
        summary_pattern="Morning meeting",
        notification_type="announce",
        offset_minutes=10,
        reminder="Grab your coat.",
    )

    notifications = EventNotifications(event).notifications(
        departure_notification_settings=_departure_notification_settings(heads_up_reminder_lead_time=10, notification_rules=[rule])
    )

    matching_offset_notifications = [n for n in notifications if n.offset == 10]
    assert len(matching_offset_notifications) == 1
    assert matching_offset_notifications[0].notification_rule is rule


