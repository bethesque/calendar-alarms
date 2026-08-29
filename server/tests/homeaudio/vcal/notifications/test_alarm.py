import pytest
import datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from homeaudio.vcal.cal.google_calendar import Event, EventNotification, LeaveForEvent, NotificationType
from homeaudio.audio.settings import NotificationRule
from homeaudio.vcal.notifications.core import NotificationTextBuilder

TIMEZONE = ZoneInfo("Australia/Melbourne")

def test_notification_text_builder_creates_text_for_travel_announcement(monkeypatch):
    base_time = datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)
    event = LeaveForEvent(
        summary="Leave for An appointment",
        description="#travel20",
        owner="Beth",
        calendar_id="id",
        start_time=datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    )
    event_notification = EventNotification(
        event=event,
        offset=5,
        type=NotificationType.ANNOUNCE
    )

    # Greeting and before/after ordering are randomised; pin them for a deterministic assertion.
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.choice", lambda seq: seq[0])
    announcement_texts = NotificationTextBuilder([event_notification], base_time).build()

    assert announcement_texts == ["Good afternoon.", "It will be time to Leave for An appointment in 5 minutes."]


def _description_event_notification(summary="Gym session", offset=0):
    event = Event(
        summary=summary,
        description="#announce",
        owner="Beth",
        calendar_id="id",
        start_time=datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE),
    )
    return EventNotification(event=event, offset=offset, type=NotificationType.ANNOUNCE)


def test_notification_text_builder_reads_bare_summary_when_no_rule_no_offset_and_lucky_roll(monkeypatch):
    base_time = datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)
    event_notification = _description_event_notification()

    # Below CHANCE_OF_ANNOUNCEMENT_WITH_NO_EXTRAS - takes the early-exit, bare-summary path.
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.random", lambda: 0.0)

    announcement_texts = NotificationTextBuilder([event_notification], base_time).build()

    assert announcement_texts == ["Gym session"]


def test_notification_text_builder_uses_full_phrasing_when_unlucky_roll(monkeypatch):
    base_time = datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)
    event_notification = _description_event_notification()

    # Above CHANCE_OF_ANNOUNCEMENT_WITH_NO_EXTRAS - falls through to the normal phrasing.
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.random", lambda: 0.999)
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.choice", lambda seq: seq[0])

    announcement_texts = NotificationTextBuilder([event_notification], base_time).build()

    assert announcement_texts == ["Good afternoon.", "It's time for Gym session."]


def test_notification_text_builder_skips_bare_summary_when_notification_rule_present(monkeypatch):
    base_time = datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)
    event_notification = _description_event_notification()
    event_notification.notification_rule = NotificationRule(summary_pattern="Gym", offset_minutes=0)

    # Even a lucky roll should never give a rule-based notification the bare-summary treatment.
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.random", lambda: 0.0)
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.choice", lambda seq: seq[0])

    announcement_texts = NotificationTextBuilder([event_notification], base_time).build()

    assert announcement_texts == ["Good afternoon.", "It's time for Gym session."]


def test_notification_text_builder_skips_bare_summary_when_offset_is_nonzero(monkeypatch):
    base_time = datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)
    event_notification = _description_event_notification(offset=20)

    # Even a lucky roll should be ignored once there's a non-zero offset.
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.random", lambda: 0.0)
    monkeypatch.setattr("homeaudio.vcal.notifications.core.random.choice", lambda seq: seq[0])

    announcement_texts = NotificationTextBuilder([event_notification], base_time).build()

    assert announcement_texts == ["Good afternoon.", "It will be time for Gym session in 20 minutes."]
