from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.audio.settings import MorningAnnouncementsSettings, SchoolAnnouncementsSettings
from homeaudio.vcal.school_announcements import is_school_holiday

MORNING_ANNOUNCEMENTS_SUMMARY = "Morning announcements"
SCHOOL_ANNOUNCEMENTS_SUMMARY = "School announcements"

class ScheduledAnnouncementType(Enum):
    MORNING_ANNOUNCEMENTS = "morning_announcements"
    SCHOOL_ANNOUNCEMENTS = "school_announcements"

@dataclass
class ScheduledAnnouncementNotification:
    summary: str
    type: ScheduledAnnouncementType
    due_datetime: datetime

def scheduled_announcement_notifications(
    morning_settings: MorningAnnouncementsSettings | None = None,
    school_settings: SchoolAnnouncementsSettings | None = None,
    calendar_source: CalendarSource = CalendarSource(),
) -> list[ScheduledAnnouncementNotification]:
    morning_settings = morning_settings or MorningAnnouncementsSettings()
    school_settings = school_settings or SchoolAnnouncementsSettings()
    calendar_days = calendar_source.load_data_from_file()

    notifications = []
    for day in calendar_days:
        is_weekend = day.date.weekday() >= 5
        tzinfo = day.date_time.tzinfo

        if morning_settings.enabled:
            scheduled_time = morning_settings.schedule.weekends if is_weekend else morning_settings.schedule.weekdays
            if scheduled_time is not None:
                notifications.append(ScheduledAnnouncementNotification(
                    summary=MORNING_ANNOUNCEMENTS_SUMMARY,
                    type=ScheduledAnnouncementType.MORNING_ANNOUNCEMENTS,
                    due_datetime=datetime.combine(day.date, scheduled_time, tzinfo=tzinfo),
                ))

        if school_settings.enabled and not is_weekend and school_settings.schedule.weekdays is not None:
            if not is_school_holiday(day.all_events(), school_settings.holiday_keywords):
                notifications.append(ScheduledAnnouncementNotification(
                    summary=SCHOOL_ANNOUNCEMENTS_SUMMARY,
                    type=ScheduledAnnouncementType.SCHOOL_ANNOUNCEMENTS,
                    due_datetime=datetime.combine(day.date, school_settings.schedule.weekdays, tzinfo=tzinfo),
                ))

    return notifications
