#!/bin/bash
# Run from project root. This script is intended to be run from a cron job.

# Do not set -e because the failure of calendar data fetching should not cause task fetching to fail

set -x

cd "$(dirname "$0")/.."
./script/refresh_calendar_data.sh
./script/refresh_task_data.sh
