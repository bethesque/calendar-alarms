#/bin/bash
# Run this file from the project root to test the check_for_alarms.py script with a manual calendar file

# Make this work on mac and on the raspberry pi.
if [ -x "/usr/bin/python3.13" ]; then
  echo "/usr/bin/python3.13 exists and is executable."
  PYTH="/usr/bin/python3.13"
else
  echo "/usr/bin/pytho3.13 is not executable or does not exist. Using python on path."
  PYTH="python"
fi

$PYTH check_for_alarms.py --base_time "2026-04-06T19:30:00+10:00" --window 5 --calendar_file tests/manual/calendar.json --handle-music-assistant
