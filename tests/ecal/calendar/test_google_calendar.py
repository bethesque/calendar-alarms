import datetime
from zoneinfo import ZoneInfo

from ecal.calendar.google_calendar import Event

TIMEZONE = ZoneInfo("Australia/Melbourne")

def test_alarm_time_with_no_offset_returns_event_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarm 20",
        start_time=start_time,
    )

    assert event.alarm_time() ==  datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)

def test_alarm_time_with_weird_tag():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarmfoo",
        start_time=start_time,
    )

    assert event.alarm_time() ==  event.start_time

def test_alarm_time_returns_offset_from_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        owner="Beth",
        summary="Morning meeting",
        description="#alarm20",
        start_time=start_time,
    )

    assert event.alarm_time() ==  datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)


def test_alarm_time_returns_none_when_no_alarm_tag_present():
    event = Event(
        owner="Beth",
        summary="No alarm event",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.alarm_time() is None


def test_alarm_time_returns_none_when_start_time_missing():
    event = Event(
        owner="Beth",
        summary="Alarm without start",
        description="#alarm20",
        start_time=None,
    )

    assert event.alarm_time() is None


def test_alarm_offset_returns_parsed_number():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.alarm_offset() == 20


def test_alarm_offset_returns_different_numbers():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm5",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.alarm_offset() == 5


def test_alarm_offset_returns_zero_when_no_number():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.alarm_offset() == 0


def test_alarm_offset_returns_zero_when_no_alarm_tag():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert event.alarm_offset() == 0


def test_alarm_offset_returns_zero_when_no_start_time():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=None,
    )

    assert event.alarm_offset() == 0


def test_alarm_offset_caches_result():
    event = Event(
        owner="Beth",
        summary="Meeting",
        description="#alarm15",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    # First call should parse and cache
    first_call = event.alarm_offset()
    # Second call should return cached value
    second_call = event.alarm_offset()

    assert first_call == 15
    assert second_call == 15
    assert first_call is second_call  # Same object reference

