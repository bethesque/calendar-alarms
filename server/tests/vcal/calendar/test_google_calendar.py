import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from homeaudio.vcal.cal.google_calendar import Event, NotificationType
from homeaudio.audio.settings import NotificationRule

TIMEZONE = ZoneInfo("Australia/Melbourne")

def test_alarm_time_with_no_offset_returns_event_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#alarm 20",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)

def test_alarm_time_with_weird_tag():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#alarmfoo",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  event.start_time

def test_alarm_time_returns_offset_from_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#alarm20",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)

def test_announce_time_returns_offset_from_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#announce20",
        start_time=start_time,
    )

    assert event.notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)

def test_alarm_time_returns_none_when_no_alarm_tag_present():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="No alarm event",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications() == []


def test_alarm_time_returns_none_when_start_time_missing():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Alarm without start",
        description="#alarm20",
        start_time=None,
    )

    assert event.notifications() == []


def test_notification_offset_returns_parsed_number():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications()[0].offset == 20


def test_notification_offset_returns_different_numbers():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm5",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications()[0].offset == 5


def test_notification_offset_returns_zero_when_no_number():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications()[0].offset == 0


def test_notification_offset_returns_zero_when_no_alarm_tag():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.notifications() == []


def test_notification_offset_returns_zero_when_no_start_time():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=None,
    )

    assert event.notifications() == []


def test_notification_offset_caches_result():
    event = Event(
        calendar_id="id",
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
        calendar_id="id",
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
        calendar_id="id",
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
        calendar_id="id",
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
        calendar_id="id",
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

def test_travel_notifications():
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#travel20",
        start_time=start_time,
    )

    notifications = event.notifications()

    assert len(notifications) == 2
    assert notifications[0].event.summary == "Leave for Morning meeting"
    assert notifications[0].type.name == "ANNOUNCE"
    assert notifications[0].offset == 5
    assert notifications[0].event.start_time == datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)

    assert notifications[1].event.summary == "Leave for Morning meeting"
    assert notifications[1].type.name == "ANNOUNCE"
    assert notifications[1].offset == 0
    assert notifications[1].event.start_time == datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)


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

    notifications = event.notifications([rule])

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

    notifications = event.notifications([rule])

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

    assert len(matching_event.notifications([rule])) == 1
    assert non_matching_event.notifications([rule]) == []
    assert no_location_event.notifications([rule]) == []


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

    assert len(event.notifications([rule])) == 1


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

    assert len(matching_event.notifications([rule])) == 1
    assert non_matching_event.notifications([rule]) == []


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

    assert len(event.notifications([rule])) == 1


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

    assert len(event.notifications([rule])) == 1


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

    assert len(all_match.notifications([rule])) == 1
    assert summary_does_not_match.notifications([rule]) == []
    assert description_does_not_match.notifications([rule]) == []
    assert address_does_not_match.notifications([rule]) == []


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

    assert len(matching_event.notifications([rule])) == 1
    assert non_matching_event.notifications([rule]) == []


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

    assert len(event.notifications([rule])) == 1


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

    assert len(event.notifications([rule])) == 1

