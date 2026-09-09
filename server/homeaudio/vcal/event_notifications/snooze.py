import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from homeaudio.audio.settings import NotificationRule
from homeaudio.audio.string_utils import json_default_encoder
from homeaudio.env import CACHE_DIRECTORY
from homeaudio.vcal.cal.google_calendar import Event, EventNotification, NotificationType, load_event

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
        "notification_rule": (
            event_notification.notification_rule.model_dump(mode="json")
            if event_notification.notification_rule
            else None
        ),
    }


def _deserialize(data: dict) -> EventNotification:
    return EventNotification(
        event=load_event(data["event"]),
        type=NotificationType[data["type"]],
        offset=data["offset"],
        notification_rule=(
            NotificationRule.model_validate(data["notification_rule"])
            if data["notification_rule"]
            else None
        ),
    )


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

    def save(self, event_notifications: list[EventNotification], replay_at: datetime) -> None:
        data = {
            "replay_at": replay_at.isoformat(),
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

    def due_event_notifications(self, now: datetime) -> list[EventNotification]:
        """Returns and clears the pending snooze if it's due at or before `now`."""
        data = self._load_raw()
        if data is None:
            return []

        replay_at = datetime.fromisoformat(data["replay_at"])
        if now < replay_at:
            return []

        self.clear()
        return [_deserialize(item) for item in data["event_notifications"]]

    def clear(self) -> None:
        Path(self.file_path).unlink(missing_ok=True)


def due_snoozed_event_notifications(now: datetime) -> list[EventNotification]:
    return SnoozeState().due_event_notifications(now)
