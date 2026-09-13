#!/bin/bash

git push
ssh travnas 'cd calendar-alarms && git pull'
ssh travnas 'systemctl --user restart calendar-alarms-http.service'
ssh travnas 'systemctl --user restart calendar-alarms.service'

ssh pi@dwainpi.local 'cd calendar-alarms && git pull'
ssh pi@dwainpi.local 'systemctl --user restart calendar-alarms-http.service'
ssh pi@dwainpi.local 'systemctl --user restart calendar-alarms.service'
