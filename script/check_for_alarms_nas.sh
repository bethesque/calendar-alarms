#!/bin/bash
# Run from project root. This script is intended to be run from a cron job to check for upcoming alarms and trigger the bluetooth connection and alarm logic if any are found.

set -Eeuo pipefail

echo "Checking for alarms at $(date)"

# --- CONFIG ---
if [ -z "${1:-}" ]; then
    echo "Usage: $0 <window>" >&2
    exit 1
fi

WINDOW="$1"

# Make this work on mac and on the raspberry pi.
if [ -x "/usr/bin/python3.13" ]; then
  echo "/usr/bin/python3.13 exists and is executable."
  PYTH="/usr/bin/python3.13"
else
  echo "/usr/bin/python is not executable or does not exist. Using python on path."
  PYTH="python"
fi

"$PYTH" check_for_alarms.py --window "$WINDOW"
