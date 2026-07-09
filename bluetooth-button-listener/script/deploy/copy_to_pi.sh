#!/bin/bash
rsync -av --files-from=<(find . -name "*.toml" -or -name "*.py" -maxdepth 2) $PWD pi@officepi.local:/home/pi/calendar-alarms/bluetooth-button-listener/
ssh officepi "systemctl --user restart bluetooth-button-listener.service"