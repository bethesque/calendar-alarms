from datetime import datetime
from pydantic import BaseModel

class TestNotificationRequest(BaseModel):
    event: dict
    notification_time: datetime

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
