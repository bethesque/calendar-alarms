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

    assert announcement_texts == ["Hi Beth. ", "It will be time to Leave for An appointment in 5 minutes."]
