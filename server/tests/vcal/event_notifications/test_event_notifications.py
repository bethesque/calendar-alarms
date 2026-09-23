import datetime
from zoneinfo import ZoneInfo

from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarSource, Event, event_from_google_dict
from homeaudio.vcal.event_notifications.events import EventNotifications, LeaveForEvent, NotificationType
from homeaudio.audio.settings import DepartureNotificationSettings

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

    assert EventNotifications(event).notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)


def test_alarm_time_with_weird_tag():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#alarmfoo",
        start_time=start_time,
    )

    assert EventNotifications(event).notifications()[0].notification_time ==  event.start_time


def test_alarm_time_returns_offset_from_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#alarm20",
        start_time=start_time,
    )

    assert EventNotifications(event).notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)


def test_announce_time_returns_offset_from_start_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#announce20",
        start_time=start_time,
    )

    assert EventNotifications(event).notifications()[0].notification_time ==  datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)


def test_alarm_time_returns_none_when_no_alarm_tag_present():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="No alarm event",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert EventNotifications(event).notifications() == []


def test_alarm_time_returns_none_when_start_time_missing():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Alarm without start",
        description="#alarm20",
        start_time=None,
    )

    assert EventNotifications(event).notifications() == []


def test_notification_offset_returns_parsed_number():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert EventNotifications(event).notifications()[0].offset == 20


def test_notification_offset_returns_different_numbers():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm5",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert EventNotifications(event).notifications()[0].offset == 5


def test_notification_offset_returns_zero_when_no_number():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert EventNotifications(event).notifications()[0].offset == 0


def test_targets_returns_words_starting_with_at_sign():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm20 @beth @kitchen",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert EventNotifications(event).notifications()[0].targets == {"beth", "kitchen"}


def test_targets_is_none_when_no_at_sign_present():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert EventNotifications(event).notifications()[0].targets is None


def test_notification_offset_returns_zero_when_no_alarm_tag():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="Regular description",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    assert EventNotifications(event).notifications() == []


def test_notification_offset_returns_zero_when_no_start_time():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm20",
        start_time=None,
    )

    assert EventNotifications(event).notifications() == []


def test_notification_offset_caches_result():
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#alarm15",
        start_time=datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE),
    )

    # First call should parse and cache
    first_call = EventNotifications(event).notifications()[0].offset
    # Second call should return cached value
    second_call = EventNotifications(event).notifications()[0].offset

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

    notifications = EventNotifications(event).notifications()

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

    notifications = EventNotifications(event).notifications()

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

    notifications = EventNotifications(event).notifications()

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

    notifications = EventNotifications(event).notifications()

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

    notifications = EventNotifications(event).notifications(departure_notification_settings=_departure_notification_settings(heads_up_reminder_lead_time=5))

    assert len(notifications) == 2
    assert notifications[0].event.summary == "Leave for Morning meeting"
    assert notifications[0].type.name == "ANNOUNCE"
    assert notifications[0].offset == 5
    assert notifications[0].event.start_time == datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)

    assert notifications[1].event.summary == "Leave for Morning meeting"
    assert notifications[1].type.name == "ANNOUNCE"
    assert notifications[1].offset == 0
    assert notifications[1].event.start_time == datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)


def _departure_notification_settings(**overrides) -> DepartureNotificationSettings:
    defaults = dict(house_to_car_minutes=5, heads_up_reminder_lead_time=10)
    defaults.update(overrides)
    return DepartureNotificationSettings(**defaults)


def test_event_with_car_departure_time_builds_computed_travel_notifications():
    # No #travel tag anywhere in the description - having a location is enough on its own.
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    car_departure_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="Some regular description",
        location="Not necessary for the actual notifications",
        start_time=start_time,
        car_departure_time=car_departure_time,
    )

    notifications = EventNotifications(event).notifications(departure_notification_settings=_departure_notification_settings(house_to_car_minutes=5, heads_up_reminder_lead_time=10))

    # walk_out_time = car_departure_time - house_to_car_minutes = 11:55
    walk_out_time = datetime.datetime(2026, 4, 28, 11, 55, tzinfo=TIMEZONE)
    assert len(notifications) == 2
    assert notifications[0].event.summary == "Leave for Morning meeting"
    assert notifications[0].type.name == "ANNOUNCE"
    assert notifications[0].offset == 10
    assert notifications[0].event.start_time == walk_out_time
    assert notifications[0].notification_time == walk_out_time - datetime.timedelta(minutes=10)

    assert notifications[1].offset == 0
    assert notifications[1].event.start_time == walk_out_time
    assert notifications[1].notification_time == walk_out_time


def test_leave_for_event_notifications_inherit_targets_from_original_event():
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    car_departure_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="Some regular description @beth @kitchen",
        location="Not necessary for the actual notifications",
        start_time=start_time,
        car_departure_time=car_departure_time,
    )

    notifications = EventNotifications(event).notifications(departure_notification_settings=_departure_notification_settings(house_to_car_minutes=5, heads_up_reminder_lead_time=10))

    assert len(notifications) == 2
    assert all(isinstance(notification.event, LeaveForEvent) for notification in notifications)
    assert notifications[0].targets == {"beth", "kitchen"}
    assert notifications[1].targets == {"beth", "kitchen"}


def test_explicit_numbered_travel_tag_takes_precedence_over_computed_car_departure_time():
    # An explicit #travel<N> tag is a manual override - it wins over any computed
    # car_departure_time, so only the tag-based notifications are added.
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#travel20",
        location="123 Fake St",
        start_time=start_time,
        car_departure_time=datetime.datetime(2026, 4, 28, 11, 0, tzinfo=TIMEZONE),
    )

    notifications = EventNotifications(event).notifications(departure_notification_settings=_departure_notification_settings())

    assert len(notifications) == 2
    assert all(n.event.start_time == datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE) for n in notifications)


def test_bare_travel_tag_does_nothing():
    # A bare #travel tag (no number) is a no-op - it neither adds its own notifications nor
    # suppresses the computed car_departure_time ones.
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#travel",
        location="123 Fake St",
        start_time=start_time,
        car_departure_time=datetime.datetime(2026, 4, 28, 11, 0, tzinfo=TIMEZONE),
    )

    notifications = EventNotifications(event).notifications(departure_notification_settings=_departure_notification_settings())

    assert len(notifications) == 2
    walk_out_time = datetime.datetime(2026, 4, 28, 10, 55, tzinfo=TIMEZONE)
    assert all(n.event.start_time == walk_out_time for n in notifications)


def test_bare_travel_tag_produces_no_notifications_without_car_departure_time():
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description="#travel",
        start_time=start_time,
    )

    assert EventNotifications(event).notifications() == []


def test_computed_departure_notification_handles_missing_description():
    # description can be None (e.g. event_from_google_dict when Google omits it); checking it for
    # a #travel<N> tag must not blow up.
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Morning meeting",
        description=None,
        location="123 Fake St",
        start_time=start_time,
        car_departure_time=datetime.datetime(2026, 4, 28, 11, 0, tzinfo=TIMEZONE),
    )

    notifications = EventNotifications(event).notifications(departure_notification_settings=_departure_notification_settings())

    assert len(notifications) == 2


def test_tag_based_notification_and_departure_notification_at_the_same_time_are_both_kept():
    # A tag-based notification fires against the target event itself, while a departure
    # notification fires against a separate LeaveForEvent - even if they land on the same
    # notification_time, they are different notifications and neither should be deduplicated away.
    start_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    car_departure_time = datetime.datetime(2026, 4, 28, 12, 0, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Meeting",
        description="#announce20",
        location="123 Fake St",
        start_time=start_time,
        car_departure_time=car_departure_time,
    )

    # house_to_car_minutes=0 puts the walk_out_time at car_departure_time (12:00), and
    # heads_up_reminder_lead_time=20 puts the computed heads-up notification at 11:40 - the same
    # notification_time and offset as the #announce20 tag notification.
    settings = _departure_notification_settings(house_to_car_minutes=0, heads_up_reminder_lead_time=20)

    notifications = EventNotifications(event).notifications(departure_notification_settings=settings)

    matching_time = datetime.datetime(2026, 4, 28, 11, 40, tzinfo=TIMEZONE)
    coincident_notifications = [n for n in notifications if n.notification_time == matching_time]

    assert len(coincident_notifications) == 2
    assert all(n.type.name == "ANNOUNCE" and n.offset == 20 for n in coincident_notifications)

    tag_notification = next(n for n in coincident_notifications if n.event is event)
    departure_notification = next(n for n in coincident_notifications if n.event is not event)
    assert departure_notification.event.summary == "Leave for Meeting"


def test_event_from_google_dict_captures_google_event_id():
    event_dict = {
        "id": "abc123",
        "summary": "Dentist",
        "description": "",
        "location": "123 Fake St",
    }

    event = event_from_google_dict(event_dict, calendar_id="id", calendar_name="Beth", owner_count=1)

    assert event.google_event_id == "abc123"


def test_google_event_id_and_car_departure_time_round_trip_through_save_and_load(tmp_path):
    calendar_source = CalendarSource(cache_file_path=str(tmp_path / "calendar.json"))
    start_time = datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    car_departure_time = datetime.datetime(2026, 4, 28, 11, 30, tzinfo=TIMEZONE)
    event = Event(
        calendar_id="id",
        owner="Beth",
        summary="Dentist",
        description="#travel",
        location="123 Fake St",
        start_time=start_time,
        google_event_id="abc123",
        car_departure_time=car_departure_time,
    )
    calendar_source.calendar_days = [CalendarDay(date=start_time.date(), timed_events=[event])]

    calendar_source.save_data_to_file()
    reloaded_event = calendar_source.load_data_from_file()[0].timed_events[0]

    assert reloaded_event.google_event_id == "abc123"
    assert reloaded_event.car_departure_time == car_departure_time

