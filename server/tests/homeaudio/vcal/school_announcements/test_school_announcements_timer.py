import subprocess
from datetime import time

from homeaudio.audio.settings import SchoolAnnouncementsSchedule
from homeaudio.vcal.school_announcements.timer import render_timer_unit, update_timer_unit


def test_render_timer_unit_includes_weekday_on_calendar_line():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))

    rendered = render_timer_unit(schedule)

    assert "OnCalendar=Mon..Fri *-*-* 08:29:00 Australia/Melbourne" in rendered
    assert "Sat,Sun" not in rendered
    assert "Unit=calendar-alarms-school-announcements.service" in rendered


def test_render_timer_unit_fires_one_lead_time_before_the_configured_weekdays_time():
    schedule = SchoolAnnouncementsSchedule(weekdays=time(7, 0, 30))

    rendered = render_timer_unit(schedule)

    assert "OnCalendar=Mon..Fri *-*-* 06:59:30 Australia/Melbourne" in rendered


def test_render_timer_unit_returns_none_when_weekdays_unset():
    schedule = SchoolAnnouncementsSchedule(weekdays=None)

    assert render_timer_unit(schedule) is None


def test_update_timer_unit_writes_file_and_reloads_systemd(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args))

    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    timer_path = tmp_path / "calendar-alarms-school-announcements.timer"

    update_timer_unit(True, schedule, timer_unit_path=timer_path)

    assert "OnCalendar=Mon..Fri" in timer_path.read_text()
    assert ["systemctl", "--user", "daemon-reload"] in calls
    assert ["systemctl", "--user", "enable", "--now", "calendar-alarms-school-announcements.timer"] in calls


def test_update_timer_unit_disables_timer_when_schedule_is_empty(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args))

    schedule = SchoolAnnouncementsSchedule(weekdays=None)
    timer_path = tmp_path / "calendar-alarms-school-announcements.timer"

    update_timer_unit(True, schedule, timer_unit_path=timer_path)

    assert not timer_path.exists()
    assert ["systemctl", "--user", "disable", "--now", "calendar-alarms-school-announcements.timer"] in calls


def test_update_timer_unit_disables_timer_when_not_enabled(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args))

    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    timer_path = tmp_path / "calendar-alarms-school-announcements.timer"

    update_timer_unit(False, schedule, timer_unit_path=timer_path)

    assert not timer_path.exists()
    assert ["systemctl", "--user", "disable", "--now", "calendar-alarms-school-announcements.timer"] in calls


def test_update_timer_unit_enables_timer_when_re_enabled(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args))

    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))
    timer_path = tmp_path / "calendar-alarms-school-announcements.timer"

    update_timer_unit(True, schedule, timer_unit_path=timer_path)

    assert timer_path.exists()
    assert ["systemctl", "--user", "enable", "--now", "calendar-alarms-school-announcements.timer"] in calls


def test_update_timer_unit_does_not_raise_when_systemctl_is_missing(tmp_path, monkeypatch):
    def raise_missing(args, **kwargs):
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr(subprocess, "run", raise_missing)

    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))

    update_timer_unit(True, schedule, timer_unit_path=tmp_path / "timer")


def test_update_timer_unit_does_not_raise_when_systemctl_fails(tmp_path, monkeypatch):
    def raise_failed(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(subprocess, "run", raise_failed)

    schedule = SchoolAnnouncementsSchedule(weekdays=time(8, 30, 0))

    update_timer_unit(True, schedule, timer_unit_path=tmp_path / "timer")
