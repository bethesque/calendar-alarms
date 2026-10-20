import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from homeaudio.audio.settings import NotificationRule
from homeaudio.audio.string_utils import json_default_encoder
from homeaudio.env import CACHE_DIRECTORY, NOTIFICATIONS_PREPARATION_LEAD_TIME_SECONDS
from homeaudio.vcal.cal.google_calendar import Event, load_timed_event
from homeaudio.vcal.event_notifications.events import EventNotification, EventNotifications, NotificationPlaytimeScheduler, NotificationSource, NotificationType

logger = logging.getLogger(__name__)

LAST_PLAYED_STATE_FILE = CACHE_DIRECTORY + "/last_played_notifications_state.json"
SNOOZE_STATE_FILE = CACHE_DIRECTORY + "/snoozed_alarm_state.json"


def _event_to_dict(event: Event) -> dict:
    return json.loads(json.dumps(event, default=json_default_encoder))


def _serialize(event_notification: EventNotification) -> dict:
    return {
        "event": _event_to_dict(event_notification.event),
        "type": event_notification.type.name,
        "offset": event_notification.offset,
        "source": event_notification.source.name,
        "notification_time": event_notification.notification_time.isoformat(),
        "play_datetime": event_notification.play_datetime.isoformat() if event_notification.play_datetime else None,
        "notification_rule": (
            event_notification.notification_rule.model_dump(mode="json")
            if event_notification.notification_rule
            else None
        ),
    }


def _deserialize(data: dict) -> EventNotification:
    event_notification = EventNotification(
        event=load_timed_event(data["event"]),
        type=NotificationType[data["type"]],
        offset=data["offset"],
        source=NotificationSource[data["source"]],
        notification_rule=(
            NotificationRule.model_validate(data["notification_rule"])
            if data["notification_rule"]
            else None
        ),
    )
    if data.get("play_datetime"):
        event_notification.play_datetime = datetime.fromisoformat(data["play_datetime"])
    return event_notification


class LastPlayedState:
    """What notification(s) last actually played - alarms and announcements alike.

    Written by check_for_notifications() whenever it has a non-empty batch to act
    on; read by the snooze endpoint (a separate HTTP-triggered process) to know
    what to re-queue. Same save/load/clear/fresh shape as MusicAssistantState.
    """

    file_path: str = LAST_PLAYED_STATE_FILE

    def save(self, event_notifications: list[EventNotification], base_time: datetime) -> None:
        data = {
            "base_time": base_time.isoformat(),
            "event_notifications": [_serialize(event_notification) for event_notification in event_notifications],
        }
        with open(self.file_path, "w") as f:
            json.dump(data, f)

    def _load_raw(self) -> dict | None:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def load(self) -> list[EventNotification]:
        data = self._load_raw()
        if data is None:
            return []
        return [_deserialize(item) for item in data["event_notifications"]]

    def load_base_time(self) -> datetime | None:
        data = self._load_raw()
        if data is None:
            return None
        return datetime.fromisoformat(data["base_time"])

    def saved_at(self) -> datetime | None:
        try:
            return datetime.fromtimestamp(os.path.getmtime(self.file_path)).astimezone()
        except FileNotFoundError:
            return None


    def base_time_does_not_match_saved_time(self) -> bool:
        """
        If the base time is not within NOTIFICATIONS_PREPARATION_LEAD_TIME_SECONDS seconds of the
        save time, then this tells us the last alarm was triggered via the UI.
        Could probably have added a flag to the method to take the guess-work out of that, but
        ah well.
        """
        base_time = self.load_base_time()
        saved_at = self.saved_at()
        if not base_time or not saved_at:
            return False
        return abs(saved_at - base_time) > timedelta(seconds=NOTIFICATIONS_PREPARATION_LEAD_TIME_SECONDS + 10)

    def fresh(self, max_age_mins: int = 5) -> bool:
        max_age_seconds = max_age_mins * 60
        try:
            mtime = os.path.getmtime(self.file_path)
        except FileNotFoundError:
            return False
        return (time.time() - mtime) < max_age_seconds

    def clear(self) -> None:
        Path(self.file_path).unlink(missing_ok=True)


class SnoozeState:
    """Pending snoozes: notifications that were stopped early and are due to
    replay at a later time. Checked by the daemon on every wake, alongside the
    regular calendar check, and cleared once replayed."""

    file_path: str = SNOOZE_STATE_FILE

    def save(self, event_notifications: list[EventNotification], replay_at: datetime, clear_at: datetime) -> None:
        data = {
            "replay_at": replay_at.isoformat(),
            "clear_at": clear_at.isoformat(),
            "event_notifications": [_serialize(event_notification) for event_notification in event_notifications],
        }
        with open(self.file_path, "w") as f:
            json.dump(data, f)

    def _load_raw(self) -> dict | None:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def next_replay_at(self) -> datetime | None:
        data = self._load_raw()
        if data is None:
            return None
        return datetime.fromisoformat(data["replay_at"])

    def pending_event_notifications(self, now: datetime, scheduler: NotificationPlaytimeScheduler) -> list[EventNotification]:
        """Returns the pending snoozed notifications with play_datetime scheduled from the replay time, without clearing them."""
        data = self._load_raw()
        if data is None:
            return []

        if "clear_at" in data and self._after_clear_at(now, data):
            return []

        replay_at = datetime.fromisoformat(data["replay_at"])
        event_notifications = [_deserialize(item) for item in data["event_notifications"]]
        for event_notification in event_notifications:
            event_notification.play_datetime = scheduler.get_play_datetime(replay_at)
        return event_notifications

    def _after_clear_at(self, now, data):
        return now >= datetime.fromisoformat(data["clear_at"])

    def due_event_notifications(self, now: datetime, scheduler: NotificationPlaytimeScheduler) -> list[EventNotification]:
        """Returns and clears the pending snooze if its scheduled play time is at or before `now`, or just clears it if it's stale at `now`."""
        data = self._load_raw()
        if data is None:
            return []

        if "clear_at" in data and self._after_clear_at(now, data):
            self.clear()
            return []

        play_datetime = scheduler.get_play_datetime(datetime.fromisoformat(data["replay_at"]))
        if now < play_datetime:
            return []

        self.clear()
        event_notifications = [_deserialize(item) for item in data["event_notifications"]]
        for event_notification in event_notifications:
            event_notification.play_datetime = play_datetime
        return event_notifications

    def clear(self) -> None:
        Path(self.file_path).unlink(missing_ok=True)


def due_snoozed_event_notifications(now: datetime, scheduler: NotificationPlaytimeScheduler) -> list[EventNotification]:
    return SnoozeState().due_event_notifications(now, scheduler)
