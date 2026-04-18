#!/bin/bash
# Run this file from the project root within a cron job to test that the bluetooth
# connection logic works correctly when run in a non-interactive environment.

# bluetoothctl
#   disconnect
# crontab -e
# * * * * * cd /home/thetrav/calendar && tests/manual/cron_bluetooth_connection_test.sh <DEVICE_MAC> >> /home/thetrav/calendar/logs/cron.log  2>&1

set -Eeuo pipefail

export DEVICE_MAC=$1

script/connect_bluetooth_speaker.sh

/usr/bin/python tests/manual/start_alarm_test.py
