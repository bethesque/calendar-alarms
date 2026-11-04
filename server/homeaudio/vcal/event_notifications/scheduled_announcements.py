from dataclasses import field, dataclass
from datetime import datetime
from enum import Enum
from homeaudio.vcal.cal.google_calendar import CalendarSource
from homeaudio.audio.settings import MorningAnnouncementsSettings, SchoolAnnouncementsSettings
from homeaudio.vcal.notification_schedule import morning_announcement_time_for_day
from homeaudio.vcal.morning_announcements import get_morning_announcement_sentences_for_api
from homeaudio.vcal.school_announcements import get_school_announcement_sentences_for_api

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
    sentences: list[str] = field(default_factory=list)

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
            scheduled_time = morning_announcement_time_for_day(morning_settings.schedule, day.date, [day])
            if scheduled_time is not None:
                notifications.append(ScheduledAnnouncementNotification(
                    summary=MORNING_ANNOUNCEMENTS_SUMMARY,
                    type=ScheduledAnnouncementType.MORNING_ANNOUNCEMENTS,
                    due_datetime=datetime.combine(day.date, scheduled_time, tzinfo=tzinfo),
                    sentences=get_morning_announcement_sentences_for_api(day.date_time, calendar_days)
                ))

        if school_settings.enabled and not is_weekend and school_settings.schedule.weekdays is not None:
            if not day.holiday:
                notifications.append(ScheduledAnnouncementNotification(
                    summary=SCHOOL_ANNOUNCEMENTS_SUMMARY,
                    type=ScheduledAnnouncementType.SCHOOL_ANNOUNCEMENTS,
                    due_datetime=datetime.combine(day.date, school_settings.schedule.weekdays, tzinfo=tzinfo),
                    sentences=get_school_announcement_sentences_for_api(day.date_time, calendar_days, school_settings)
                ))

    return notifications
