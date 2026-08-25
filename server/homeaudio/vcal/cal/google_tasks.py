import datetime
import json
import logging
import os.path
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from homeaudio.audio.string_utils import json_default_encoder
from homeaudio.vcal.cal.google_calendar import load_google_creds

logger = logging.getLogger(__name__)

@dataclass
class Task:
    id: str
    title: str
    task_list_id: str
    task_list_title: str
    notes: str | None = None
    status: str = "needsAction"
    due_date: datetime.date | None = None


def list_google_task_lists(creds):
    try:
        service = build("tasks", "v1", credentials=creds, cache_discovery=False)
        items = []
        request = service.tasklists().list(maxResults=100)
        while request is not None:
            result = request.execute()
            items.extend(result.get("items", []))
            request = service.tasklists().list_next(request, result)
        return items
    except HttpError as error:
        logger.error(f"An error occurred listing task lists: {error}")
        return []


def list_google_tasks(creds, task_list_id, due_min: str, due_max: str):
    try:
        service = build("tasks", "v1", credentials=creds, cache_discovery=False)
        items = []
        request = service.tasks().list(
            tasklist=task_list_id,
            maxResults=100,
            showCompleted=False,
            showDeleted=False,
            showHidden=False,
            dueMin=due_min,
            dueMax=due_max,
        )
        while request is not None:
            result = request.execute()
            items.extend(result.get("items", []))
            request = service.tasks().list_next(request, result)
        return items
    except HttpError as error:
        logger.error(f"An error occurred listing tasks for list {task_list_id}: {error}")
        return []


def build_task(task_dict, task_list_id, task_list_title) -> Task:
    due = task_dict.get("due")
    return Task(
        id=task_dict["id"],
        title=task_dict.get("title", ""),
        notes=task_dict.get("notes"),
        status=task_dict.get("status", "needsAction"),
        # The due timestamp always marks UTC midnight of the due date; only
        # the date portion is meaningful (the API discards the time of day).
        due_date=datetime.date.fromisoformat(due[:10]) if due else None,
        task_list_id=task_list_id,
        task_list_title=task_list_title,
    )


def get_tasks_for_date(creds, target_date: datetime.date) -> list[Task]:
    # "due" is always UTC midnight of the due date, so bound the window on UTC
    # date boundaries rather than converting target_date to local time.
    due_min = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=datetime.timezone.utc).isoformat()
    due_max = datetime.datetime.combine(target_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=datetime.timezone.utc).isoformat()

    tasks = []
    for task_list in list_google_task_lists(creds):
        for task_dict in list_google_tasks(creds, task_list["id"], due_min, due_max):
            task = build_task(task_dict, task_list["id"], task_list.get("title", ""))
            logger.info(f"Found task {task}")
            tasks.append(task)
    return tasks


@dataclass
class TaskSource:
    cache_file_path: str
    tasks: list[Task] = None
    creds: any = None

    def load_creds(self):
        self.creds = load_google_creds()
        return self.creds

    def creds_valid(self):
        return self.creds and self.creds.valid

    def fetch_data(self, target_date: datetime.date | None = None):
        target_date = target_date or datetime.date.today()
        self.tasks = get_tasks_for_date(self.creds, target_date)
        return self.tasks

    def save_data_to_file(self):
        data_json = json.dumps(self.tasks, sort_keys=True, default=json_default_encoder)
        with open(self.cache_file_path, "w") as f:
            f.write(data_json)

    def cache_file_exists(self):
        return os.path.exists(self.cache_file_path)
