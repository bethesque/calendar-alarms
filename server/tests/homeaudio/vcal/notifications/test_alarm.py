import pytest
import datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from homeaudio.vcal.cal.google_calendar import Event, EventNotification, LeaveForEvent, NotificationType
from homeaudio.audio.settings import NotificationRule
from homeaudio.vcal.notifications.core import NotificationTextBuilder

TIMEZONE = ZoneInfo("Australia/Melbourne")

def test_notification_text_builder_creates_text_for_travel_announcement():
    base_time = datetime.datetime(2026, 4, 28, 12, 10, tzinfo=TIMEZONE)
    event = LeaveForEvent(
        summary="Leave for An appointment",
        description="#travel20",
        owner="Beth",
        start_time=datetime.datetime(2026, 4, 28, 12, 30, tzinfo=TIMEZONE)
    )
    event_notification = EventNotification(
        event=event,
        offset=5,
        type=NotificationType.ANNOUNCE
    )
    announcement_texts = NotificationTextBuilder([event_notification], base_time).build()
    assert announcement_texts[0] == "It will be time to Leave for An appointment in 5 minutes"
