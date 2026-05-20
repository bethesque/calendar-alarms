function calendar-alarms-snapserver-logs {
    journalctl SYSLOG_IDENTIFIER=calendar-alarms-snapserver "$@"
}

function calendar-alarms-snapserver-status {
    sudo systemctl status snapserver "$@"
}

function calendar-alarms-snapserver-start {
    sudo systemctl start snapserver "$@"
}

function calendar-alarms-snapserver-stop {
    sudo systemctl stop snapserver "$@"
}

function calendar-alarms-snapserver-restart {
    sudo systemctl restart snapserver "$@"
}

function calendar-alarms-snapserver-test {
    mpc clear
    mpc add /usr/share/sounds/alsa/Front_Center.wav
    mpc volume 50
    mpc play
    sleep 5
    mpc clear
}

function calendar-alarms-http-status {
    systemctl --user status calendar-alarms-http
}

function calendar-alarms-http-start {
    systemctl --user start calendar-alarms-http
}

function calendar-alarms-http-restart {
    systemctl --user restart calendar-alarms-http
}

function calendar-alarms-http-stop {
    systemctl --user stop calendar-alarms-http
}

function calendar-alarms-http-logs {
    journalctl SYSLOG_IDENTIFIER=calendar-alarms-http "$@"
}
