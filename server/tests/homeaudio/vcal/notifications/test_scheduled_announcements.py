from datetime import datetime, time
from zoneinfo import ZoneInfo

from homeaudio.audio.settings import (
    MorningAnnouncementsSchedule,
    MorningAnnouncementsSettings,
    SchoolAnnouncementsSchedule,
    SchoolAnnouncementsSettings,
)
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarSource, Event
from homeaudio.vcal.event_notifications.scheduled_announcements import ScheduledAnnouncementNotification, scheduled_announcement_notifications

TIMEZONE = ZoneInfo("Australia/Melbourne")


def _calendar_source_for(calendar_days, monkeypatch):
    calendar_source = CalendarSource(cache_file_path="")
    monkeypatch.setattr(calendar_source, "load_data_from_file", lambda: calendar_days)
    return calendar_source


def test_scheduled_announcement_notifications_includes_morning_and_school_on_a_weekday(monkeypatch):
    monday = CalendarDay(date=datetime(2026, 4, 6, tzinfo=TIMEZONE).date())
    morning_settings = MorningAnnouncementsSettings(schedule=MorningAnnouncementsSchedule(weekdays=time(7, 17), weekends=time(9, 57)))
    school_settings = SchoolAnnouncementsSettings(schedule=SchoolAnnouncementsSchedule(weekdays=time(8, 30)))

    notifications = scheduled_announcement_notifications(
        morning_settings, school_settings, _calendar_source_for([monday], monkeypatch)
    )

    assert notifications == [
        ScheduledAnnouncementNotification(summary="Morning announcements", due_datetime=datetime(2026, 4, 6, 7, 17, tzinfo=TIMEZONE)),
        ScheduledAnnouncementNotification(summary="School announcements", due_datetime=datetime(2026, 4, 6, 8, 30, tzinfo=TIMEZONE)),
    ]


def test_scheduled_announcement_notifications_uses_weekend_morning_schedule_and_skips_school(monkeypatch):
    saturday = CalendarDay(date=datetime(2026, 4, 11, tzinfo=TIMEZONE).date())
    morning_settings = MorningAnnouncementsSettings(schedule=MorningAnnouncementsSchedule(weekdays=time(7, 17), weekends=time(9, 57)))
    school_settings = SchoolAnnouncementsSettings(schedule=SchoolAnnouncementsSchedule(weekdays=time(8, 30)))

    notifications = scheduled_announcement_notifications(
        morning_settings, school_settings, _calendar_source_for([saturday], monkeypatch)
    )

    assert notifications == [
        ScheduledAnnouncementNotification(summary="Morning announcements", due_datetime=datetime(2026, 4, 11, 9, 57, tzinfo=TIMEZONE)),
    ]


def test_scheduled_announcement_notifications_skips_disabled_announcements(monkeypatch):
    monday = CalendarDay(date=datetime(2026, 4, 6, tzinfo=TIMEZONE).date())
    morning_settings = MorningAnnouncementsSettings(enabled=False)
    school_settings = SchoolAnnouncementsSettings(enabled=False)

    notifications = scheduled_announcement_notifications(
        morning_settings, school_settings, _calendar_source_for([monday], monkeypatch)
    )

    assert notifications == []


def test_scheduled_announcement_notifications_skips_school_announcement_on_a_holiday(monkeypatch):
    holiday_event = Event(owner="Beth", calendar_id="id", summary="School holidays", description="", start_time=None)
    monday = CalendarDay(date=datetime(2026, 4, 6, tzinfo=TIMEZONE).date(), whole_day_events=[holiday_event])
    morning_settings = MorningAnnouncementsSettings(schedule=MorningAnnouncementsSchedule(weekdays=time(7, 17), weekends=time(9, 57)))
    school_settings = SchoolAnnouncementsSettings(schedule=SchoolAnnouncementsSchedule(weekdays=time(8, 30)))

    notifications = scheduled_announcement_notifications(
        morning_settings, school_settings, _calendar_source_for([monday], monkeypatch)
    )

    assert notifications == [
        ScheduledAnnouncementNotification(summary="Morning announcements", due_datetime=datetime(2026, 4, 6, 7, 17, tzinfo=TIMEZONE)),
    ]
