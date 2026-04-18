#/bin/bash
# Run this file from the project root to test the check_for_alarms.py script with a manual calendar file

python check_for_alarms.py --base_time "2026-04-06T19:30:00+10:00" --window 5 --calendar_file tests/manual/calendar.json
