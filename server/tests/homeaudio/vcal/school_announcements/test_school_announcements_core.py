from datetime import datetime, time

from homeaudio.audio.settings import SchoolAnnouncementsSchedule
from homeaudio.vcal.school_announcements.core import _announcement_due


def test_announcement_due_true_when_scheduled_time_is_at_start_of_window():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    base_time = datetime(2024, 1, 1, 8, 30, 0)  # Monday

    assert _announcement_due(base_time, 5, schedule) is True


def test_announcement_due_true_when_scheduled_time_is_within_window():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    base_time = datetime(2024, 1, 1, 8, 26, 0)  # Monday, 4 minutes before

    assert _announcement_due(base_time, 5, schedule) is True


def test_announcement_due_false_when_scheduled_time_has_already_passed():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    base_time = datetime(2024, 1, 1, 8, 31, 0)  # Monday, one minute after

    assert _announcement_due(base_time, 5, schedule) is False


def test_announcement_due_false_when_scheduled_time_is_outside_the_window():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    base_time = datetime(2024, 1, 1, 8, 20, 0)  # Monday, 10 minutes before a 5 minute window

    assert _announcement_due(base_time, 5, schedule) is False


def test_announcement_due_false_at_window_end_boundary():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    base_time = datetime(2024, 1, 1, 8, 25, 0)  # Monday, exactly `window` minutes before

    assert _announcement_due(base_time, 5, schedule) is False


def test_announcement_due_false_on_saturday():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    base_time = datetime(2024, 1, 6, 8, 30, 0)  # Saturday

    assert _announcement_due(base_time, 5, schedule) is False


def test_announcement_due_false_on_sunday():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    base_time = datetime(2024, 1, 7, 8, 30, 0)  # Sunday

    assert _announcement_due(base_time, 5, schedule) is False


def test_announcement_due_false_when_schedule_weekdays_is_none():
    schedule = SchoolAnnouncementsSchedule(weekdays=None)
    base_time = datetime(2024, 1, 1, 8, 30, 0)  # Monday

    assert _announcement_due(base_time, 5, schedule) is False
