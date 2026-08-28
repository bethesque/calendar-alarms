function calendar-alarms-snapserver-logs {
    sudo journalctl -u snapserver "$@"
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

function calendar-alarms-snapserver-api-status {
    curl -X POST http://127.0.0.1:1780/jsonrpc \
        -H "Content-Type: application/json" \
        -d '{"id":1,"jsonrpc":"2.0","method":"Server.GetStatus"}' | jq .
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

function calendar-alarms-status {
    systemctl --user status calendar-alarms
}

function calendar-alarms-start {
    systemctl --user start calendar-alarms
}

function calendar-alarms-restart {
    systemctl --user restart calendar-alarms
}

function calendar-alarms-stop {
    systemctl --user stop calendar-alarms
}

function calendar-alarms-logs {
    journalctl SYSLOG_IDENTIFIER=calendar-alarms "$@"
}

function calendar-alarms-morning-announcements-logs {
    journalctl SYSLOG_IDENTIFIER=calendar-alarms-morning-announcements "$@"
}
