#!/bin/bash
# Run from project root. Long-running alternative to check_for_alarms.sh - sleeps
# between checks itself instead of being invoked by cron/a systemd timer every 5
# minutes. Intended to be run under systemd (Type=simple, Restart=always), not cron.

set -Eeuo pipefail

echo "Starting alarm check daemon at $(date)"

# Make this work on mac and on the raspberry pi.
if [ -x "/usr/bin/python3.13" ]; then
  PYTH="/usr/bin/python3.13"
else
  echo "/usr/bin/python3.13 is not executable or does not exist. Using python on path."
  PYTH="python"
fi

# exec replaces this shell with the python process, so systemd's SIGTERM on stop
# goes straight to it instead of being caught by an intermediate shell.
exec "$PYTH" calendar_alarms_daemon.py
