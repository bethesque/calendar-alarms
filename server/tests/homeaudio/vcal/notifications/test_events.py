from datetime import datetime
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import EventNotificationSettings, NotificationRule
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.vcal.notifications.events import get_calendar_refreshed_at, get_event_notifications

TIMEZONE = ZoneInfo("Australia/Melbourne")


def test_get_event_notifications_ignores_disabled_rules():
    date_string = "2026-04-06T09:00:00+10:00"
    base_time = datetime.fromisoformat(date_string)

    days = [
        {
            "date": "2026-04-06",
            "date_time": date_string,
            "timed_events": [
                {
                    "description": "",
                    "end_time": None,
                    "owner": "Beth",
                    "calendar_id": "id",
                    "recurring": False,
                    "start_time": date_string,
                    "summary": "Gym"
                }
            ],
            "whole_day_events": []
        }
    ]
    calendar_data = CalendarSource(cache_file_path="").load_data_from_any(days)

    enabled_rule = NotificationRule(summary_pattern="Gym", notification_type="announce", offset_minutes=0, enabled=True)
    disabled_rule = NotificationRule(summary_pattern="Gym", notification_type="alarm", offset_minutes=0, enabled=False)
    settings = EventNotificationSettings(notification_rules=[enabled_rule, disabled_rule])

    notifications = get_event_notifications(base_time, 5, calendar_data, settings)

    assert len(notifications) == 1
    assert notifications[0].notification_rule is enabled_rule


def test_get_calendar_refreshed_at_returns_the_stored_refreshed_at(tmp_path):
    cache_file = str(tmp_path / "calendar.json")
    refreshed_at = datetime(2026, 4, 28, 9, 0, tzinfo=TIMEZONE)
    CalendarSource(cache_file_path=cache_file, calendar_days=[], refreshed_at=refreshed_at).save_data_to_file()

    result = get_calendar_refreshed_at(CalendarSource(cache_file_path=cache_file))

    assert result == refreshed_at


def test_get_calendar_refreshed_at_returns_none_when_never_refreshed(tmp_path):
    cache_file = str(tmp_path / "calendar.json")
    CalendarSource(cache_file_path=cache_file, calendar_days=[], refreshed_at=None).save_data_to_file()

    result = get_calendar_refreshed_at(CalendarSource(cache_file_path=cache_file))

    assert result is None
