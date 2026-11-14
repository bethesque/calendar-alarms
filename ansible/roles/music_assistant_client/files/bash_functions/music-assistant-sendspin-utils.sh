function music-assistant-sendspin-logs {
    journalctl SYSLOG_IDENTIFIER=wispd "$@"
}

function music-assistant-sendspin-logs-tail {
    journalctl SYSLOG_IDENTIFIER=wispd -f -n 50 "$@"
}

function music-assistant-sendspin-status {
    systemctl --user status wispd "$@"
}

function music-assistant-sendspin-start {
    systemctl --user start wispd "$@"
}

function music-assistant-sendspin-stop {
    systemctl --user stop wispd "$@"
}

function music-assistant-sendspin-restart {
    systemctl --user restart wispd "$@"
}
