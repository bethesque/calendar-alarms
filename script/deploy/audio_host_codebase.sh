#!/bin/bash

git push
ssh travnas 'cd calendar-alarms && git pull'
ssh travnas 'systemctl --user restart calendar-alarms-http.service'