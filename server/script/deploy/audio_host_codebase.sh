#!/bin/bash

git push
echo "Updating travnas"
ssh travnas 'cd calendar-alarms && git pull'
echo "Restarting calendar-alarms-http.service"
ssh travnas 'systemctl --user restart calendar-alarms-http.service'
echo "Restarting calendar-alarms.service"
ssh travnas 'systemctl --user restart calendar-alarms.service'

echo "Updating dwainpi"
ssh pi@dwainpi 'cd calendar-alarms && git pull'
echo "Restarting calendar-alarms-http.service"
ssh pi@dwainpi 'systemctl --user restart calendar-alarms-http.service'
echo "Restarting calendar-alarms.service"
ssh pi@dwainpi 'systemctl --user restart calendar-alarms.service'
