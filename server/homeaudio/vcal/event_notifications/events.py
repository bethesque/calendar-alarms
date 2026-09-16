import logging
from datetime import datetime, timedelta
from homeaudio.vcal.cal.google_calendar import CalendarDay, EventNotification, NotificationType, CalendarSource
from homeaudio.audio.settings import EventNotificationSettings, DepartureNotificationSettings
from homeaudio.vcal.departure_time import TravelTimeCache, car_departure_time_for_event, relevant_dates

logger = logging.getLogger(__name__)

class NotificationFinder:
    def __init__(self, calendar_days: list[CalendarDay], base_time, window, notification_rules=None, departure_notification_settings: DepartureNotificationSettings | None = None):
        self.calendar_days = calendar_days
        self.base_time = base_time
        self.window = window
        self.notification_rules = notification_rules or []
        self.departure_notification_settings = departure_notification_settings


    def find_notification_events(self):
        start, end = self._get_time_window()

        matching_events = []

        for day in self.calendar_days:
            for event in day.timed_events:
                event_notifications = event.notifications_within_window(start, end, self.notification_rules, self.departure_notification_settings)
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

def get_event_notifications(base_time, window, calendar_data: list[CalendarDay], event_notification_settings: EventNotificationSettings, departure_notification_settings: DepartureNotificationSettings | None = None):
    notification_rules = event_notification_settings.enabled_notification_rules()
    alarm_finder = NotificationFinder(calendar_data, base_time, window, notification_rules, departure_notification_settings)
    event_notifications = alarm_finder.find_notification_events()
    return event_notifications

def get_all_event_notifications(event_notification_settings: EventNotificationSettings | None = None, calendar_source: CalendarSource = CalendarSource(), departure_notification_settings: DepartureNotificationSettings | None = None):
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    calendar_days = calendar_source.load_data_from_file()

    notification_rules = event_notification_settings.enabled_notification_rules()
    notifications = []
    for day in calendar_days:
        for event in day.timed_events:
            notifications.extend(event.notifications(notification_rules, departure_notification_settings))

    return notifications

def get_all_events(calendar_source: CalendarSource = CalendarSource()):
    calendar_days = calendar_source.load_data_from_file()
    events_by_day = [
        (calendar_day.date, event.start_time is not None, event.start_time, event)
        for calendar_day in calendar_days
        for event in calendar_day.all_events()
    ]
    events_by_day.sort(key=lambda item: (item[0], item[1], item[2] or datetime.min))
    return [event for *_, event in events_by_day]

def get_calendar_refreshed_at(calendar_source: CalendarSource = CalendarSource()) -> datetime | None:
    calendar_source.load_data_from_file()
    return calendar_source.refreshed_at

def update_calendar_travel_times() -> None:
    departure_notification_settings = DepartureNotificationSettings()
    calendar_source = CalendarSource()
    calendar_days = calendar_source.load_data_from_file()

    now = datetime.now().astimezone()
    cache = TravelTimeCache.load()

    # Because of the way multi-day events get allocated to multiple CalendarDays, there is a filter
    # here to find the CalendarDays worth checking to see if we should add a car_departure_time
    # but there is also another check on the start time of each event with the departure logic.
    relevant_days = [day for day in calendar_days if day.date in relevant_dates(now)]
    try:
        for day in relevant_days:
            for event in day.timed_events:
                try:
                    event.car_departure_time = car_departure_time_for_event(event, departure_notification_settings, cache, now)
                    if event.car_departure_time:
                        logger.info(f"Set departure time for {event.summary} to {event.car_departure_time}")
                except Exception:
                    logger.exception("Error computing car_departure_time for event '%s'", event.summary)

        cache.prune(now)
    finally:
        cache.save()
        calendar_source.save_data_to_file()

