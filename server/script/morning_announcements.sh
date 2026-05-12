#!/bin/bash
# Run from project root. This script is intended to be run from a cron job to play the morning announcements.

set -Eeuo pipefail

echo "Morning announcements at $(date)"

# Make this work on mac and on the raspberry pi.
if [ -x "/usr/bin/python3.13" ]; then
  PYTH="/usr/bin/python3.13"
else
  echo "/usr/bin/python3.13 is not executable or does not exist. Using python on path."
  PYTH="python"
fi

"$PYTH" morning_announcements.py "$@"
