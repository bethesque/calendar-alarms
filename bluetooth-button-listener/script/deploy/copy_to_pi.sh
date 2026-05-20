#!/bin/bash
rsync -av --files-from=<(find . -name "*.toml" -or -name "*.py" -maxdepth 2) $PWD pi@officepi.local:/home/pi/bluetooth-button/