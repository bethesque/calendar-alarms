#!/bin/bash
# Run from project root. This script is intended to be run from a cron job.

set -Eeuo pipefail

echo "Refreshing calendar data at $(date)"

# Make this work on mac and on the raspberry pi.
if [ -x "/usr/bin/python3.13" ]; then
  echo "/usr/bin/python3.13 exists and is executable."
  PYTH="/usr/bin/python3.13"
else
  echo "/usr/bin/python3.13 is not executable or does not exist. Using python on path."
  PYTH="python"
fi

"$PYTH" -c "from ecal.cli import refresh_calendar_data; refresh_calendar_data()"
