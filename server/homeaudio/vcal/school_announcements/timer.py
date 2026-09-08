import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from homeaudio.env import TIMEZONE, SYSTEMD_USER_DIR

from homeaudio.audio.settings import SchoolAnnouncementsSchedule

logger = logging.getLogger(__name__)

SERVICE_NAME = "calendar-alarms-school-announcements"

# The timer fires this long before the configured announcement time, so play_school_announcements
# has time to build the audio file before sleeping until the exact moment to play it.
LEAD_TIME = timedelta(minutes=1)

DEFAULT_TIMER_UNIT_PATH = Path(SYSTEMD_USER_DIR) / f"{SERVICE_NAME}.timer"

TIMER_UNIT_TEMPLATE = """[Unit]
Description=Calendar Alarms School Announcements Timer

[Timer]
{on_calendar_lines}
Unit={service_name}.service
Persistent=false

[Install]
WantedBy=timers.target
"""


def render_timer_unit(schedule: SchoolAnnouncementsSchedule) -> str | None:
    """Renders the timer unit for `schedule`, or None if weekdays isn't set."""
    if schedule.weekdays is None:
        return None

    trigger_time = (datetime.combine(datetime.min, schedule.weekdays) - LEAD_TIME).time()

    return TIMER_UNIT_TEMPLATE.format(
        on_calendar_lines=f"OnCalendar=Mon..Fri *-*-* {trigger_time.strftime('%H:%M:%S')} {TIMEZONE}",
        service_name=SERVICE_NAME,
    )


def update_timer_unit(enabled: bool, schedule: SchoolAnnouncementsSchedule, timer_unit_path: Path = DEFAULT_TIMER_UNIT_PATH) -> None:
    """Writes the live systemd timer unit reflecting `enabled`/`schedule` and reloads/restarts it.

    This is separate from the ansible-managed .j2 template (which just seeds the timer on a
    fresh deploy) - it updates the timer actually running on this host, so a schedule or
    enabled/disabled change saved through the admin UI takes effect immediately without
    needing a redeploy.
    """
    rendered = render_timer_unit(schedule) if enabled else None

    try:
        if rendered:
            timer_unit_path.parent.mkdir(parents=True, exist_ok=True)
            timer_unit_path.write_text(rendered)
        else:
            reason = "disabled" if not enabled else "schedule is empty"
            logger.info("School announcements %s; disabling %s.timer", reason, SERVICE_NAME)
            subprocess.run(["systemctl", "--user", "disable", "--now", f"{SERVICE_NAME}.timer"], check=True)
            return


        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", f"{SERVICE_NAME}.timer"], check=True)
        logger.info("Updated %s.timer for the new school announcements schedule", SERVICE_NAME)
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.exception(
            "Could not update the live %s.timer (systemctl unavailable, e.g. on a dev machine?)", SERVICE_NAME
        )
