#!/bin/bash

git sparse-checkout add server
git pull
if [ "$1" = "-i" ]; then
  python3 -m pip install -e "."
fi
systemctl --user restart calendar-alarms.service
systemctl --user restart calendar-alarms-http.service
echo "Waiting 10 seconds for restart..."
sleep 10
systemctl --user status calendar-alarms.service
systemctl --user status calendar-alarms-http.service
