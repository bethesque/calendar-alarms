function calendar-alarms-snapclient-logs {
    journalctl SYSLOG_IDENTIFIER=calendar-alarms-snapclient "$@"
}

function calendar-alarms-snapclient-status {
    systemctl --user status calendar-alarms-snapclient "$@"
}

function calendar-alarms-snapclient-start {
    systemctl --user start calendar-alarms-snapclient "$@"
}

function calendar-alarms-snapclient-stop {
    systemctl --user stop calendar-alarms-snapclient "$@"
}

function calendar-alarms-snapclient-restart {
    systemctl --user restart calendar-alarms-snapclient "$@"
}

function audio-client-speaker-test {
    speaker-test -c 2 -t wav -l 1
}

function audio-client-http-logs {
    journalctl SYSLOG_IDENTIFIER=audio-client-http "$@"
}

function audio-client-http-status {
    systemctl --user status audio-client-http
}

function audio-client-http-start {
    systemctl --user start audio-client-http
}

function audio-client-http-restart {
    systemctl --user restart audio-client-http
}

function audio-client-http-stop {
    systemctl --user stop audio-client-http
}

function audio-client-http-test {
    curl -X POST "${AUDIO_CLIENT_URL}/audio/toggle"
}
