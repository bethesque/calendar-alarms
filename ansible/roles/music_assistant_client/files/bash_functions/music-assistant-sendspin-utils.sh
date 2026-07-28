function music-assistant-sendspin-logs {
    journalctl SYSLOG_IDENTIFIER=sendspin-armv6 "$@"
}

function music-assistant-sendspin-status {
    systemctl --user status sendspin-armv6 "$@"
}

function music-assistant-sendspin-start {
    systemctl --user start sendspin-armv6 "$@"
}

function music-assistant-sendspin-stop {
    systemctl --user stop sendspin-armv6 "$@"
}

function music-assistant-sendspin-restart {
    systemctl --user restart sendspin-armv6 "$@"
}
