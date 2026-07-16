import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from vcal.cal.google_calendar import Event, NotificationType
from vcal.settings import NotificationRule

TIMEZONE = ZoneInfo("Australia/Melbourne")

def test_alarm_time_with_no_offset_returns_event_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarm 20",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)

def test_alarm_time_with_weird_tag():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarmfoo",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  event.start_time

def test_alarm_time_returns_offset_from_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarm20",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)

def test_announce_time_returns_offset_from_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#announce20",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)

def test_alarm_time_returns_none_when_no_alarm_tag_present():
    event = Event(
        owner="Beth",
        summary="No alarm event",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications() == []


def test_alarm_time_returns_none_when_start_time_missing():
    event = Event(
        owner="Beth",
        summary="Alarm without start",
        description="#alarm20",
        start_time=None,
    )

    assert event.notifications() == []


def test_notification_offset_returns_parsed_number():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications()[0].offset == 20


def test_notification_offset_returns_different_numbers():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm5",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications()[0].offset == 5


def test_notification_offset_returns_zero_when_no_number():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications()[0].offset == 0


def test_notification_offset_returns_zero_when_no_alarm_tag():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications() == []


def test_notification_offset_returns_zero_when_no_start_time():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=None,
    )

    assert event.notifications() == []


def test_notification_offset_caches_result():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm15",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    # First call should parse and cache
    first_call = event.notifications()[0].offset
    # Second call should return cached value
    second_call = event.notifications()[0].offset

    assert first_call == 15
    assert second_call == 15
    assert first_call is second_call  # Same object reference

def test_notifications_returns_no_alarm_event_notification():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description=None,
        start_time=start_time,
    )

    notifications = event.notifications()

    assert len(notifications) == 0

def test_notifications_returns_alarm_event_notification():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarm20",
        start_time=start_time,
    )

    notifications = event.notifications()

    assert len(notifications) == 1
    assert notifications[0].type.name == "ALARM"
    assert notifications[0].offset == 20
    assert notifications[0].event is event


def test_notifications_returns_announce_event_notification_without_offset():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#announce",
        start_time=start_time,
    )

    notifications = event.notifications()

    assert len(notifications) == 1
    assert notifications[0].type.name == "ANNOUNCE"
    assert notifications[0].offset == 0


def test_notifications_can_parse_multiple_tags_in_description():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarm10 #announce5",
        start_time=start_time,
    )

    notifications = event.notifications()

    assert len(notifications) == 2
    assert notifications[0].type.name == "ALARM"
    assert notifications[0].offset == 10
    assert notifications[1].type.name == "ANNOUNCE"
    assert notifications[1].offset == 5


def test_notifications_support_description_rules():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Gym session",
        description="This is a gym workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        pattern="gym",
        notification_type="alarm",
        offset_minutes=75,
    )

    notifications = event.notifications([rule])

    assert len(notifications) == 1
    assert notifications[0].type == NotificationType.ALARM
    assert notifications[0].offset == 75
    assert notifications[0].notification_time == datetime.datetime(2026, 4, 28, 10, 45, tzinfo=TIMEZONE)


def test_notification_rule_rejects_invalid_notification_type():
    with pytest.raises(ValidationError):
        NotificationRule(pattern="gym", notification_type="beep")


def test_notifications_description_rules_require_matching_owner():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    matching_event = Event(
        owner="Beth",
        summary="Gym session",
        description="This is a gym workout",
        start_time=start_time,
    )
    non_matching_event = Event(
        owner="Alex",
        summary="Gym session",
        description="This is a gym workout",
        start_time=start_time,
    )

    rule = NotificationRule(
        pattern="gym",
        notification_type="alarm",
        offset_minutes=75,
        owner="Beth",
    )

    assert len(matching_event.notifications([rule])) == 1
    assert non_matching_event.notifications([rule]) == []

