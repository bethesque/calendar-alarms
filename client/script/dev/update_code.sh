#!/bin/bash

script_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
command="cd calendar-alarms && git sparse-checkout add client && git pull && systemctl --user restart audio-client-http"
command="systemctl --user restart audio-client-http"
"$script_dir"/../../../script/dev/run_command_on_clients.sh "${command}"
