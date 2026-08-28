import logging
import subprocess
from pathlib import Path
from homeaudio.env import TIMEZONE, SYSTEMD_USER_DIR

from homeaudio.audio.settings import MorningAnnouncementsSchedule

logger = logging.getLogger(__name__)

SERVICE_NAME = "calendar-alarms-morning-announcements"

DEFAULT_TIMER_UNIT_PATH = Path(SYSTEMD_USER_DIR) / f"{SERVICE_NAME}.timer"

TIMER_UNIT_TEMPLATE = """[Unit]
Description=Calendar Alarms Morning Announcements Timer

[Timer]
{on_calendar_lines}
Unit={service_name}.service
Persistent=false

[Install]
WantedBy=timers.target
"""


def render_timer_unit(schedule: MorningAnnouncementsSchedule) -> str | None:
    """Renders the timer unit for `schedule`, or None if neither weekdays nor weekends is set."""
    on_calendar_lines = []
    if schedule.weekdays is not None:
        on_calendar_lines.append(f"OnCalendar=Mon..Fri *-*-* {schedule.weekdays.strftime('%H:%M:%S')} {TIMEZONE}")
    if schedule.weekends is not None:
        on_calendar_lines.append(f"OnCalendar=Sat,Sun *-*-* {schedule.weekends.strftime('%H:%M:%S')} {TIMEZONE}")

    if not on_calendar_lines:
        return None

    return TIMER_UNIT_TEMPLATE.format(
        on_calendar_lines="\n".join(on_calendar_lines),
        service_name=SERVICE_NAME,
    )


def update_timer_unit(schedule: MorningAnnouncementsSchedule, timer_unit_path: Path = DEFAULT_TIMER_UNIT_PATH) -> None:
    """Writes the live systemd timer unit reflecting `schedule` and reloads/restarts it.

    This is separate from the ansible-managed .j2 template (which just seeds the timer on a
    fresh deploy) - it updates the timer actually running on this host, so a schedule change
    saved through the admin UI takes effect immediately without needing a redeploy.
    """
    rendered = render_timer_unit(schedule)

    try:
        if rendered:
            timer_unit_path.parent.mkdir(parents=True, exist_ok=True)
            timer_unit_path.write_text(rendered)
        else:
            logger.info("Morning announcements schedule is empty; disabling %s.timer", SERVICE_NAME)
            subprocess.run(["systemctl", "--user", "disable", "--now", f"{SERVICE_NAME}.timer"], check=True)
            return


        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", f"{SERVICE_NAME}.timer"], check=True)
        logger.info("Updated %s.timer for the new morning announcements schedule", SERVICE_NAME)
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.exception(
            "Could not update the live %s.timer (systemctl unavailable, e.g. on a dev machine?)", SERVICE_NAME
        )
