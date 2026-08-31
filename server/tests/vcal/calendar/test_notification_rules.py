import sys
from pathlib import Path
from datetime import datetime

from homeaudio.audio.settings import NotificationRule

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from homeaudio.vcal.notifications.core import NotificationFinder, NotificationTextBuilder
from homeaudio.vcal.cal.google_calendar import CalendarSource

def test_notification_rule_with_reminder_e2e(monkeypatch):
    date_string = "2026-04-06T00:00:00+10:00"
    base_time = datetime.fromisoformat("2026-04-06T00:00:00+10:00")

    days = [
        {
            "date":  base_time.strftime("%Y-%m-%d"),
            "date_time": date_string,
            "timed_events": [
                {
                    "description": "#announce",
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
    rule = NotificationRule(summary_pattern="Gym", notification_type='announce', offset_minutes=0, reminder="Remember to eat.")
    alarm_finder = NotificationFinder(calendar_data, base_time, 5, [rule])
    event_notifications = alarm_finder.find_notification_events()

    # Greeting and before/after ordering are randomised; pin them for a deterministic assertion.
    monkeypatch.setattr("homeaudio.vcal.notifications.text.random.choice", lambda seq: seq[0])
    announcement_texts = NotificationTextBuilder(event_notifications, base_time).build()

    assert "It's time for Gym." in announcement_texts
    assert "Remember to eat." in announcement_texts
