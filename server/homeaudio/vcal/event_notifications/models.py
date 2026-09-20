from datetime import datetime
from pydantic import BaseModel, computed_field

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

    @computed_field
    @property
    def duration_seconds(self) -> int:
        return 60 if self.type == "announce" else 300

class NotificationsResponse(BaseModel):
    notifications: list[NotificationResponseItem]
