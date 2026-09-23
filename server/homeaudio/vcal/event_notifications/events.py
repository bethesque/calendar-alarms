import logging
import re
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarSource, Event
from homeaudio.audio.settings import EventNotificationSettings, DepartureNotificationSettings
from homeaudio.vcal.departure_time import TravelTimeCache, car_departure_time_for_event, relevant_dates
from homeaudio.audio.settings import NotificationRule, DepartureNotificationSettings

logger = logging.getLogger(__name__)

@dataclass
class LeaveForEvent(Event):
    target_event: Event | None = None

class NotificationType(Enum):
    ALARM = 1
    ANNOUNCE = 2


@dataclass
class EventNotification:
    event: "Event"
    type: NotificationType
    offset: int
    notification_time: datetime = field(init=False)
    notification_rule: NotificationRule | None = None

    def __post_init__(self):
        self.notification_time = self.event.start_time - timedelta(minutes=self.offset)

    def same_excluding_notification_rule(self, other: "EventNotification") -> bool:
        return (
            self.event == other.event
            and self.event.__class__ == other.event.__class__
            and self.type == other.type
            and self.offset == other.offset
            and self.notification_time == other.notification_time
        )

def _pattern_matches(pattern: str | None, value: str | None) -> bool:
    """A pattern that is empty/unset always matches; otherwise it must be a
    case-insensitive substring of value."""
    if not pattern:
        return True
    if not value:
        return False
    return pattern.lower() in value.lower()

def _calendar_id_matches(rule_calendar_id: str | None, event_calendar_id: str | None) -> bool:
    """An unset rule calendar_id matches any calendar. An unset event calendar_id
    matches any rule. Otherwise the two IDs must match exactly."""
    if not rule_calendar_id or not event_calendar_id:
        return True
    return rule_calendar_id == event_calendar_id

def notifications_from_rules(event_to_match: "Event", rules: list[NotificationRule], event_for_notification: "Event | None" = None) -> list[EventNotification]:
    notifications: list[EventNotification] = []
    # When checking for departure notifications, the matching logic is done on the target event, but the notification is
    # added for the LeaveForEvent

    event_for_notification = event_for_notification or event_to_match
    if not event_to_match.start_time:
        return notifications

    for rule in rules:
        if not notification_rule_matches_event(event_to_match, rule):
            continue

        notifications.append(EventNotification(
            event=event_for_notification,
            type=NotificationType[rule.notification_type.upper()],
            offset=rule.offset_minutes,
            notification_rule = rule
        ))
    return notifications

def notification_rule_matches_event(event: "Event", rule: NotificationRule) -> bool:
    if not _calendar_id_matches(rule.calendar_id, event.calendar_id):
        return False
    if not _pattern_matches(rule.summary_pattern, event.summary):
        return False
    if not _pattern_matches(rule.description_pattern, event.description):
        return False
    if not _pattern_matches(rule.location_pattern, event.location):
        return False
    return True


class EventNotifications:
    def __init__(self, event: Event) -> None:
        self.event = event

    def notifications(self, rules: list[NotificationRule] | None = None, departure_notification_settings: DepartureNotificationSettings | None = None) -> list[EventNotification]:
        notifications = []

        departure_notification_settings = departure_notification_settings or DepartureNotificationSettings()

        # Add the notifications from rules first because they have reminders, and will be used in preference
        # to notifications sourced from the description if there is a duplicate.
        if rules:
            notifications.extend(notifications_from_rules(self.event, rules))


        self._add_computed_departure_notifications(notifications, departure_notification_settings)

        self._add_notifications_from_description(notifications, departure_notification_settings)

        return self._deduplicate_notifications(notifications)

    def _add_notifications_from_description(self, notifications, departure_notification_settings: DepartureNotificationSettings):
        if self.event.description and self.event.start_time:
            matches = re.findall(r"#(alarm|announce|travel)(\d+)?", self.event.description)
            if matches:
                for match in matches:
                    tag, offset = match

                    offset_int = int(offset) if offset else 0

                    if tag == "travel":
                        if offset:
                            self.add_departure_notifications_from_tag(notifications, offset_int, departure_notification_settings)
                    else:
                        type_enum = NotificationType[tag.upper()]
                        notifications.append(EventNotification(type=type_enum, offset=offset_int, event=self.event))

    def notifications_within_window(self, start_time, end_time, rules: list[NotificationRule] | None = None, departure_notification_settings: DepartureNotificationSettings | None = None):
        notifications_in_window = []
        for event_notification in self.notifications(rules, departure_notification_settings):
            if start_time <= event_notification.notification_time < end_time:
                notifications_in_window.append(event_notification)
        return notifications_in_window

    def add_departure_notifications_from_tag(self, notifications, offset_int, departure_notification_settings: DepartureNotificationSettings):
        """
            Add notification for leaving time, and for 5 minutes before leaving time
        """
        walk_out_time = self.event.start_time - timedelta(minutes=offset_int)
        self._add_departure_notifications(notifications, walk_out_time, departure_notification_settings)

    def _add_computed_departure_notifications(self, notifications, departure_notification_settings: DepartureNotificationSettings):
        """
            Add notification for leaving time, and for the configured lead time before leaving time
        """
        if self.event.car_departure_time and not self._has_travel_tag_with_number():
            walk_out_time = self.event.car_departure_time - timedelta(minutes=departure_notification_settings.house_to_car_minutes)
            self._add_departure_notifications(notifications, walk_out_time, departure_notification_settings)

    def _has_travel_tag_with_number(self):
        return (self.event.description and re.findall(r"#travel(\d+)", self.event.description))

    def _add_departure_notifications(self, notifications, walk_out_time: datetime, departure_notification_settings: DepartureNotificationSettings):
        leave_event = self.leave_for_event(walk_out_time)

        # Do the rules ones first because they'll override the non-rules ones if there are notifications at the same time
        notifications.extend(notifications_from_rules(self.event, departure_notification_settings.notification_rules, leave_event))

        notifications.append(EventNotification(type=NotificationType.ANNOUNCE, offset=departure_notification_settings.heads_up_reminder_lead_time, event=leave_event))
        notifications.append(EventNotification(type=NotificationType.ANNOUNCE, offset=0, event=leave_event))


    def leave_for_event(self, walk_out_time) -> "LeaveForEvent":
        """
        Returns an event that represents leaving for another event.
        """
        return LeaveForEvent(
                            owner=self.event.owner,
                            calendar_id=self.event.calendar_id,
                            owner_count=self.event.owner_count,
                            summary=f"Leave for {self.event.summary}",
                            description=self.event.description,
                            start_time=walk_out_time,
                            end_time=self.event.start_time,
                            location=self.event.location,
                            target_event=self.event
                        )

    def _deduplicate_notifications(self, notifications):
        deduplicated_notifications = []
        for notification in notifications:
            if any(existing.same_excluding_notification_rule(notification) and not notification.notification_rule for existing in deduplicated_notifications):
                continue
            deduplicated_notifications.append(notification)

        return deduplicated_notifications

def round_down_to_interval(dt: datetime, interval_minutes: int) -> datetime:
    minute = (dt.minute // interval_minutes) * interval_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)

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
                event_notifications = EventNotifications(event).notifications_within_window(start, end, self.notification_rules, self.departure_notification_settings)
                matching_events.extend(event_notifications)

        self._log_results(start, end, matching_events)

        return matching_events


    def _get_time_window(self):
        start_time = round_down_to_interval(self.base_time, self.window)
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
            notifications.extend(EventNotifications(event).notifications(notification_rules, departure_notification_settings))

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

