from datetime import datetime
from pydantic import BaseModel

class TestNotificationRequest(BaseModel):
    event: dict
    play_datetime: datetime
    notification_time: datetime
    notification_type: str

class PlayScheduledAnnouncementRequest(BaseModel):
    base_time: datetime | None = None

class EventSummaryResponse(BaseModel):
    summary: str

class NotificationResponseItem(BaseModel):
    event: EventSummaryResponse
    type: str
    due_datetime: datetime
    play_datetime: datetime
    duration_seconds: int

class NotificationsResponse(BaseModel):
    notifications: list[NotificationResponseItem]
