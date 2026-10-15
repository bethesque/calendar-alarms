import logging
import re
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from datetime import datetime, timedelta, tzinfo
from homeaudio.vcal.cal.google_calendar import CalendarDay, CalendarDayList, CalendarSource, Event
from homeaudio.audio.settings import EventNotificationSchedule, EventNotificationSettings, DepartureNotification, DepartureTimeRule, NotificationRule
from homeaudio.vcal.departure_time import TravelTimeCache, car_departure_time_for_event, relevant_dates
from homeaudio.vcal.notification_schedule import round_down_to_interval, event_notification_time_range_for_day, within_event_notification_operating_hours
from homeaudio.env import NOTIFICATIONS_CHECK_INTERVAL_MINUTES
logger = logging.getLogger(__name__)

@dataclass
class LeaveForEvent(Event):
    target_event: Event | None = None

class NotificationType(Enum):
    ALARM = 1
    ANNOUNCE = 2

class NotificationSource(Enum):
    NOTIFICATION_RULE = (1, "Notification rule")

    ALARM_DESCRIPTION_TAG = (2, "#alarm in event description")
    ANNOUNCE_DESCRIPTION_TAG = (3, "#announce in event description")

    DEPART_DESCRIPTION_TAG = (4, "#depart tag in description")
    DEPART_DESCRIPTION_TAG_AND_HEADS_UP = (5, "#depart tag in description and heads-up reminder")
    DEPART_DESCRIPTION_TAG_AND_NOTIFICATION_RULE = (6, "#depart tag in description and notification rule")

    LOCATION = (7, "Location (calculated travel time)")
    LOCATION_AND_HEADS_UP = (8, "Location (calculated travel time) and heads-up reminder")
    LOCATION_AND_NOTIFICATION_RULE = (9, "Location (calculated travel time) and notification rule")

    DEPARTURE_TIME_RULE = (10, "Departure time rule")
    DEPARTURE_TIME_RULE_AND_HEADS_UP = (11, "Departure time rule and heads-up reminder")
    DEPARTURE_TIME_RULE_AND_NOTIFICATION_RULE = (12, "Departure time rule and notification rule")

    def __init__(self, _, label):
        self._label = label

    @property
    def label(self) -> str:
        return self._label

    def with_notification_rule(self):
        return NotificationSource[f"{self.name}_AND_NOTIFICATION_RULE"]

    def with_heads_up_reminder(self):
        return NotificationSource[f"{self.name}_AND_HEADS_UP"]

    @staticmethod
    def for_tag(tag) -> "NotificationSource":
        return NotificationSource[f"{tag.upper()}_DESCRIPTION_TAG"]


@dataclass
class EventNotification:
    event: "Event"
    type: NotificationType
    offset: int
    source: NotificationSource
    notification_time: datetime = field(init=False)
    play_datetime: datetime | None = field(default=None, init=False) # The datetime it will actually play, taking into account the NOTIFICATIONS_CHECK_INTERVAL_MINUTES and the schedule hours for the day
    notification_rule: NotificationRule | None = None
    targets: frozenset[str] | None = None

    def __post_init__(self):
        self.notification_time = self.event.start_time - timedelta(minutes=self.offset)

    def same_excluding_notification_rule(self, other: "EventNotification") -> bool:
        return (
            self.event == other.event
            and self.event.__class__ == other.event.__class__
            and self.type == other.type
            and self.offset == other.offset
            and self.notification_time == other.notification_time
            and self.play_datetime == other.play_datetime
        )


def _pattern_matches(pattern: str | None, value: str | None) -> bool:
    """A pattern that is empty/unset always matches; otherwise it must be a
    case-insensitive substring of value."""
    if not pattern:
        return True
    if not value:
        return False
    return pattern.lower() in value.lower()

def _targets_from_description(description: str | None) -> frozenset[str] | None:
    if not description:
        return None
    targets = set(re.findall(r"@(\w+)", description))
    return frozenset(targets) or None

def _calendar_id_matches(rule_calendar_id: str | None, event_calendar_id: str | None) -> bool:
    """An unset rule calendar_id matches any calendar. An unset event calendar_id
    matches any rule. Otherwise the two IDs must match exactly."""
    if not rule_calendar_id or not event_calendar_id:
        return True
    return rule_calendar_id == event_calendar_id

def notifications_from_rules(event_to_match: "Event", rules: list[NotificationRule], source: NotificationSource | None = None, event_for_notification: "Event | None" = None) -> list[EventNotification]:
    notifications: list[EventNotification] = []
    # When checking for departure notifications, the matching logic is done on the target event, but the notification is
    # added for the LeaveForEvent

    event_for_notification = event_for_notification or event_to_match

    for rule in rules:
        if not notification_rule_matches_event(event_to_match, rule):
            continue

        notifications.append(EventNotification(
            event=event_for_notification,
            type=NotificationType[rule.notification_type.upper()],
            offset=rule.offset_minutes,
            notification_rule = rule,
            targets=_targets_from_description(event_for_notification.description),
            source= source.with_notification_rule() if source else NotificationSource.NOTIFICATION_RULE
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

def departure_time_rule_matches_event(event: "Event", rule: DepartureTimeRule) -> bool:
    if not _pattern_matches(rule.summary_pattern, event.summary):
        return False
    return True


def round_to_nearest_minute(dt: datetime):
    return (dt + timedelta(seconds=30)).replace(second=0, microsecond=0)

class EventNotifications:
    def __init__(self, event: Event, scheduler: "NotificationPlaytimeScheduler") -> None:
        self.event = event
        self.scheduler = scheduler

    def notifications(self, rules: list[NotificationRule] | None = None, departure_notifications: DepartureNotification | None = None) -> list[EventNotification]:

        event_start_notifications = []
        departure_time_notifications = []


        departure_notifications = departure_notifications or EventNotificationSettings().departure_notifications

        # Add the notifications from rules first because they have reminders, and will be used in preference
        # to notifications sourced from the description if there is a duplicate.

        event_start_notification_rules = rules or []
        event_start_notifications.extend(notifications_from_rules(self.event, event_start_notification_rules))

        self._add_event_start_notifications_from_description(event_start_notifications)

        self._add_departure_time_notifications(departure_time_notifications, departure_notifications)

        notifications = self._deduplicate_notifications(event_start_notifications) + self._deduplicate_notifications(departure_time_notifications)

        for notification in notifications:
            notification.play_datetime = self.scheduler.get_play_datetime(notification.notification_time)

        return notifications

    def _add_event_start_notifications_from_description(self, notifications):
        if self.event.description:
            matches = re.findall(r"#(alarm|announce)(\d+)?", self.event.description)
            if matches:
                for match in matches:
                    tag, offset = match

                    offset_int = int(offset) if offset else 0

                    type_enum = NotificationType[tag.upper()]
                    notifications.append(EventNotification(
                        type=type_enum,
                        offset=offset_int,
                        event=self.event,
                        targets=_targets_from_description(self.event.description),
                        source=NotificationSource.for_tag(tag)
                    ))

    def _add_departure_time_notifications(self, notifications, departure_notifications: DepartureNotification):
        walk_out_time = self._get_walk_out_time_from_description_tag()

        if walk_out_time:
            self._add_departure_notifications(notifications, walk_out_time, departure_notifications, NotificationSource.DEPART_DESCRIPTION_TAG)
            return

        if self.event.car_departure_time:
            walk_out_time = round_to_nearest_minute(self.event.car_departure_time - timedelta(minutes=departure_notifications.location_based_departure_times.house_to_car_minutes))
            self._add_departure_notifications(notifications, walk_out_time, departure_notifications, NotificationSource.LOCATION)
            return

        walk_out_time = self._get_walk_out_time_from_departure_rules(departure_notifications.departure_time_rules)
        if walk_out_time:
            self._add_departure_notifications(notifications, walk_out_time, departure_notifications, NotificationSource.DEPARTURE_TIME_RULE)

    def _get_walk_out_time_from_description_tag(self) -> datetime | None:
        if self.event.description:
            offsets = [int(match) for match in re.findall(r"#depart(\d+)", self.event.description)]
            if offsets:
                offset_max = max(offsets)
                if len(offsets) > 1:
                    logger.warning(f"Event {self.event.summary} had multiple depart tags: {offsets}. Using offset={offset_max}.")
                walk_out_time = self.event.start_time - timedelta(minutes=offset_max)
                return walk_out_time

        return None

    def _get_walk_out_time_from_departure_rules(self, departure_time_rules: list[DepartureTimeRule]) -> datetime | None:
        matching_rules = [ rule for rule in departure_time_rules if departure_time_rule_matches_event(self.event, rule)]

        if matching_rules:
            departure_minutes = max([rule.departure_minutes for rule in matching_rules])
            if len(matching_rules) > 1:
                logger.warning(f"Event {self.event.summary} matched multiple departure time rules: {matching_rules}. Using departure_minutes={departure_minutes}.")
            return self.event.start_time - timedelta(minutes=departure_minutes)
        else:
            return None

    def _add_departure_notifications(self, notifications, walk_out_time: datetime, departure_notifications: DepartureNotification, source: NotificationSource):
        leave_event = self.leave_for_event(walk_out_time)

        # Do the rules ones first because they'll override the non-rules ones if there are notifications at the same time
        notifications.extend(notifications_from_rules(self.event, departure_notifications.notification_rules, source, leave_event))

        leave_event_targets = _targets_from_description(leave_event.description)
        notifications.append(EventNotification(type=NotificationType.ANNOUNCE, offset=departure_notifications.heads_up_reminder_lead_time, event=leave_event, targets=leave_event_targets, source=source.with_heads_up_reminder()))
        notifications.append(EventNotification(type=NotificationType.ANNOUNCE, offset=0, event=leave_event, targets=leave_event_targets, source=source))


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
                            location=self.event.location,
                            target_event=self.event
                        )

    def _deduplicate_notifications(self, notifications):
        """
        Any notification with a notification_rule attatched overrides one which is otherwise the same but has
        no notification rule.
        """
        deduplicated_notifications = []
        for notification in notifications:
            if any(existing.same_excluding_notification_rule(notification) and not notification.notification_rule for existing in deduplicated_notifications):
                continue
            deduplicated_notifications.append(notification)

        return deduplicated_notifications

class NotificationPlaytimeScheduler:
    def __init__(self, tz: tzinfo, schedule: EventNotificationSchedule, calendar_days: CalendarDayList, window: int):
        self.tz = tz
        self.schedule = schedule
        self.calendar_days = calendar_days
        self.window = window

    def get_play_datetime(self, notification_time: datetime) -> datetime:
        local_time = notification_time.astimezone(self.tz)
        datetime_range = event_notification_time_range_for_day(self.schedule, local_time.date(), self.calendar_days, local_time.tzinfo, self.window)
        last_tick = datetime_range.end - timedelta(minutes=self.window)
        return max(datetime_range.start, min(round_down_to_interval(local_time, self.window), last_tick))

class NotificationFinder:
    def __init__(self, calendar_days: CalendarDayList, base_time, scheduler: NotificationPlaytimeScheduler, notification_rules=None, departure_notifications: DepartureNotification | None = None):
        self.calendar_days = calendar_days
        self.base_time = base_time
        self.scheduler = scheduler
        self.notification_rules = notification_rules or []
        self.departure_notifications = departure_notifications


    def find_notification_events(self):
        if self.base_time != round_down_to_interval(self.base_time, self.scheduler.window) and within_event_notification_operating_hours(self.base_time, self.scheduler.schedule, self.calendar_days, self.scheduler.window):
            logger.warning("Base time %s is not a multiple of the %s minute check interval, so notifications may be missed", self.base_time.isoformat(), self.scheduler.window)

        matching_events = []

        for day in self.calendar_days:
            for event in day.timed_events:
                event_notifications = EventNotifications(event, self.scheduler).notifications(self.notification_rules, self.departure_notifications)
                matching_events.extend(n for n in event_notifications if n.play_datetime == self.base_time)

        self._log_results(matching_events)

        return matching_events

    def _log_results(self, results:list[EventNotification]):
        logger.info("Finding notifications to play at %s", self.base_time.isoformat())

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

def get_event_notifications(base_time, scheduler: NotificationPlaytimeScheduler, calendar_data: CalendarDayList, event_notification_settings: EventNotificationSettings):
    notification_rules = event_notification_settings.enabled_notification_rules()
    alarm_finder = NotificationFinder(calendar_data, base_time, scheduler, notification_rules, event_notification_settings.departure_notifications)
    event_notifications = alarm_finder.find_notification_events()
    return event_notifications

def get_all_event_notifications(event_notification_settings: EventNotificationSettings | None = None, calendar_source: CalendarSource = CalendarSource()):
    event_notification_settings = event_notification_settings or EventNotificationSettings()
    calendar_days = calendar_source.load_data_from_file()

    notification_rules = event_notification_settings.enabled_notification_rules()
    scheduler = NotificationPlaytimeScheduler(datetime.now().astimezone().tzinfo, event_notification_settings.schedule, calendar_days, NOTIFICATIONS_CHECK_INTERVAL_MINUTES)
    notifications = []
    for day in calendar_days:
        for event in day.timed_events:
            notifications.extend(EventNotifications(event, scheduler).notifications(notification_rules, event_notification_settings.departure_notifications))

    return notifications

def get_calendar_days(calendar_source: CalendarSource = CalendarSource()) -> CalendarDayList:
    return calendar_source.load_data_from_file()

def get_calendar_refreshed_at(calendar_source: CalendarSource = CalendarSource()) -> datetime | None:
    calendar_source.load_data_from_file()
    return calendar_source.refreshed_at

def update_calendar_travel_times() -> None:
    departure_notifications = EventNotificationSettings().departure_notifications
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
                    event.car_departure_time = car_departure_time_for_event(event, departure_notifications.location_based_departure_times, cache, now)
                    if event.car_departure_time:
                        logger.info(f"Set departure time for {event.summary} to {event.car_departure_time}")
                except Exception:
                    logger.exception("Error computing car_departure_time for event '%s'", event.summary)

        cache.prune(now)
    finally:
        cache.save()
        calendar_source.save_data_to_file()

