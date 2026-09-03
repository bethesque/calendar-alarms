import logging
from datetime import datetime, timedelta
from homeaudio.vcal.cal.google_calendar import CalendarDay, EventNotification, NotificationType, CalendarSource
from homeaudio.audio.settings import EventNotificationSettings
from homeaudio.env import CALENDAR_DATA_DIRECTORY

DATA_FILE = CALENDAR_DATA_DIRECTORY + "/calendar.json"

logger = logging.getLogger(__name__)

class NotificationFinder:
    def __init__(self, calendar_days: list[CalendarDay], base_time, window, notification_rules=None):
        self.calendar_days = calendar_days
        self.base_time = base_time
        self.window = window
        self.notification_rules = notification_rules or []


    def find_notification_events(self):
        start, end = self._get_time_window()

        matching_events = []

        for day in self.calendar_days:
            for event in day.timed_events:
                event_notifications = event.notifications_within_window(start, end, self.notification_rules)
                matching_events.extend(event_notifications)

        self._log_results(start, end, matching_events)

        return matching_events


    def _get_time_window(self):
        # Round down to nearest multiple of WINDOW
        minute = (self.base_time.minute // self.window) * self.window
        start_time = self.base_time.replace(minute=minute, second=0, microsecond=0)
        end_time = start_time + timedelta(minutes=self.window)
        return start_time, end_time

    def _log_results(self, start, end, results:list[EventNotification]):
        logger.info(
            "Time window: %s → %s (WINDOW=%d mins)",
            start.isoformat(),
            end.isoformat(),
            self.window)

        for event_notification in results:
            logger.info(
                "Matched event: %s | %s with %s offset by %d mins at %s)",
                event_notification.event.start_time,
                event_notification.event.summary,
                event_notification.type.name.lower(),
                event_notification.offset,
                event_notification.notification_time
            )
        logger.info("Total matched events: %d", len(results))
        return results

def get_event_notifications(base_time, window, calendar_data: list[CalendarDay], event_notification_settings: EventNotificationSettings):
    notification_rules = event_notification_settings.enabled_notification_rules()
    alarm_finder = NotificationFinder(calendar_data, base_time, window, notification_rules)
    event_notifications = alarm_finder.find_notification_events()
    return event_notifications

def get_all_event_notifications(event_notification_settings: EventNotificationSettings = EventNotificationSettings(), calendar_source: CalendarSource = CalendarSource(DATA_FILE)):
    calendar_days = calendar_source.load_data_from_file()

    notification_rules = event_notification_settings.enabled_notification_rules()
    notifications = []
    for day in calendar_days:
        for event in day.timed_events:
            notifications.extend(event.notifications(notification_rules))

    return notifications

def get_all_events(calendar_source: CalendarSource = CalendarSource(DATA_FILE)):
    calendar_days = calendar_source.load_data_from_file()
    events_by_day = [
        (calendar_day.date, event.start_time is not None, event.start_time, event)
        for calendar_day in calendar_days
        for event in calendar_day.all_events()
    ]
    events_by_day.sort(key=lambda item: (item[0], item[1], item[2] or datetime.min))
    return [event for *_, event in events_by_day]

def get_calendar_refreshed_at(calendar_source: CalendarSource = CalendarSource(DATA_FILE)) -> datetime | None:
    calendar_source.load_data_from_file()
    return calendar_source.refreshed_at

