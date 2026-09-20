import json
import logging
from datetime import datetime
from pathlib import Path
import threading
from queue import Queue
from fastapi import APIRouter, Request, Response
from fastapi.templating import Jinja2Templates
from homeaudio.vcal.morning_announcements import play_morning_announcements
from homeaudio.vcal.school_announcements import play_school_announcements
from homeaudio.audio.scene import scene_for_env
from homeaudio.vcal.core import stop_alarm, test_alarm, test_announcement, test_notification, mute_alarm_for_area_of_player, replay_last_notification, snooze_alarm
from homeaudio.vcal.event_notifications.events import get_all_event_notifications, get_all_events, get_calendar_refreshed_at, update_calendar_travel_times, round_down_to_interval
from homeaudio.vcal.event_notifications.models import TestNotificationRequest, EventSummaryResponse, NotificationResponseItem, NotificationsResponse
from homeaudio.vcal.cal.google_calendar import LeaveForEvent, EventNotification
from homeaudio.vcal.cli import refresh_calendar_data
from homeaudio.audio.settings import SnapcastSettings, DepartureNotificationSettings
from homeaudio.audio.string_utils import json_default_encoder
from homeaudio.env import APP_NAME, NOTIFICATIONS_CHECK_INTERVAL_MINUTES

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

def format_notification_for_api(
    notification: EventNotification,
    check_interval_minutes: int = NOTIFICATIONS_CHECK_INTERVAL_MINUTES,
) -> NotificationResponseItem:
    return NotificationResponseItem(
        event=EventSummaryResponse(summary=notification.event.summary),
        type=notification.type.name.lower(),
        due_datetime=notification.notification_time,
        play_datetime=round_down_to_interval(notification.notification_time, check_interval_minutes),
    )

def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "")

class AlarmHandler:
    def __init__(self):
        self.queue = Queue(maxsize=1)
        self._pending = False
        self._lock = threading.Lock()

        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            action = self.queue.get()
            scene = scene_for_env().__class__
            try:
                if action.get("snooze", False):
                    snooze_alarm(scene.restore_after_alarm)
                else:
                    stop_alarm(scene.restore_after_alarm)
            finally:
                with self._lock:
                    self._pending = False
                self.queue.task_done()

    def stop_alarm(self, snooze: bool = False) -> str:
        with self._lock:
            if self._pending:
                return "Alarm currently being stopped/snoozed"

            self._pending = True

        try:
            self.queue.put_nowait({ "snooze": snooze } )
            return "Stopping alarm..."
        except Exception:
            with self._lock:
                self._pending = False
            return "Alarm currently being stopped/snoozed"

    def mute_area_of_player(self, player: str) -> str:
        threading.Thread(target=mute_alarm_for_area_of_player, args=(player,SnapcastSettings()), daemon=True).start()
        return f"Muting area for {player}"


    def test_alarm(self) -> str:
        threading.Thread(target=test_alarm, daemon=True).start()
        return "Testing alarm..."

    def test_announcement(self) -> str:
        threading.Thread(target=test_announcement, daemon=True).start()
        return "Testing announcement..."

    def test_notification(self, event: dict, notification_time: datetime) -> str:
        threading.Thread(target=test_notification, args=(event, notification_time), daemon=True).start()
        return "Testing notification..."

    def play_morning_announcements(self) -> str:
        threading.Thread(target=play_morning_announcements, daemon=True).start()
        return "Playing morning announcements..."

    def play_school_announcements(self) -> str:
        threading.Thread(target=play_school_announcements, daemon=True).start()
        return "Playing school announcements..."

    def refresh_calendar_data(self) -> str:
        refresh_calendar_data()
        return "Calendar data refreshed"

    def recompute_departure_times(self) -> str:
        if not DepartureNotificationSettings().enabled:
            return "Departure notifications are disabled"
        threading.Thread(target=update_calendar_travel_times, daemon=True).start()
        return "Recomputing departure times..."

    def replay_last_notification(self) -> str:
        threading.Thread(target=replay_last_notification, daemon=True).start()
        return "Replaying last notification"

class AlarmRoutes:
    def __init__(self):
        self.alarm_handler = AlarmHandler()
        self.router = APIRouter()

        self.router.add_api_route("/", self.index, methods=["GET"], name="alarm_index")

        self.router.add_api_route(
            "/stop",
            self.stop_alarm_endpoint,
            methods=["POST"],
            name="alarm_stop",
        )

        self.router.add_api_route(
            "/mute/area-of/{player}",
            self.mute_area_endpoint,
            methods=["POST"],
            name="alarm_mute",
        )

        self.router.add_api_route(
            "/test",
            self.test_alarm_endpoint,
            methods=["POST"],
            name="alarm_test",
        )

        self.router.add_api_route(
            "/test-announcement",
            self.test_announcement_endpoint,
            methods=["POST"],
            name="announcement_test",
        )

        self.router.add_api_route(
            "/morning-announcements",
            self.play_morning_announcements_endpoint,
            methods=["POST"],
            name="play_morning_announcements",
        )

        self.router.add_api_route(
            "/school-announcements",
            self.play_school_announcements_endpoint,
            methods=["POST"],
            name="play_school_announcements",
        )

        self.router.add_api_route(
            "/refresh-calendar-data",
            self.refresh_calendar_data_endpoint,
            methods=["POST"],
            name="refresh_calendar_data",
        )

        self.router.add_api_route(
            "/recompute-departure-times",
            self.recompute_departure_times_endpoint,
            methods=["POST"],
            name="recompute_departure_times",
        )

        self.router.add_api_route(
            "/calendar-refreshed-at",
            self.calendar_refreshed_at_endpoint,
            methods=["GET"],
            name="calendar_refreshed_at",
        )

        self.router.add_api_route(
            "/notifications",
            self.notifications,
            methods=["GET"],
            name="notifications",
        )

        self.router.add_api_route(
            "/events",
            self.events,
            methods=["GET"],
            name="events",
        )

        self.router.add_api_route(
            "/replay",
            self.replay_last_notification,
            methods=["POST"],
            name="replay_last_notification",
        )

        self.router.add_api_route(
            "/snooze",
            self.snooze_endpoint,
            methods=["POST"],
            name="alarm_snooze",
        )

        self.router.add_api_route(
            "/test-notification",
            self.test_notification_endpoint,
            methods=["POST"],
            name="test_notification",
        )

    async def index(self, request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
        )

    async def stop_alarm_endpoint(self):
        message = self.alarm_handler.stop_alarm()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def mute_area_endpoint(self, player: str):
        message = self.alarm_handler.mute_area_of_player(player)
        return Response(content=message, status_code=202, media_type="text/plain")

    async def test_alarm_endpoint(self):
        message = self.alarm_handler.test_alarm()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def test_announcement_endpoint(self):
        message = self.alarm_handler.test_announcement()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def play_morning_announcements_endpoint(self):
        message = self.alarm_handler.play_morning_announcements()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def play_school_announcements_endpoint(self):
        message = self.alarm_handler.play_school_announcements()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def refresh_calendar_data_endpoint(self):
        message = self.alarm_handler.refresh_calendar_data()
        return Response(content=message, status_code=200, media_type="text/plain")

    async def recompute_departure_times_endpoint(self):
        message = self.alarm_handler.recompute_departure_times()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def calendar_refreshed_at_endpoint(self):
        refreshed_at = get_calendar_refreshed_at()
        return Response(content=refreshed_at.isoformat() if refreshed_at else "", status_code=200, media_type="text/plain")

    async def notifications(self, request: Request):
        event_notifications = sorted(get_all_event_notifications(), key=lambda notification: notification.notification_time)

        if _wants_json(request):
            return NotificationsResponse(
                notifications=[format_notification_for_api(n) for n in event_notifications]
            )

        notifications = [
            (
                notification,
                json.dumps(
                    notification.event.target_event if isinstance(notification.event, LeaveForEvent) else notification.event,
                    default=json_default_encoder,
                ),
            )
            for notification in event_notifications
        ]
        return templates.TemplateResponse(
            request=request,
            name="notifications.html",
            context={"notifications": notifications},
        )

    async def events(self, request: Request):
        events = get_all_events()
        return templates.TemplateResponse(
            request=request,
            name="events.html",
            context={"events": events},
        )

    async def replay_last_notification(self):
        message = self.alarm_handler.replay_last_notification()
        return Response(content=message, status_code=202, media_type="text/plain")

    async def snooze_endpoint(self):
        message = self.alarm_handler.stop_alarm(snooze=True)
        return Response(content=message, status_code=202, media_type="text/plain")

    async def test_notification_endpoint(self, payload: TestNotificationRequest):
        message = self.alarm_handler.test_notification(payload.event, payload.notification_time)
        return Response(content=message, status_code=202, media_type="text/plain")

    def _with_page_context(self, context: dict)-> dict:
        context["title_prefix"] = APP_NAME
        return context
