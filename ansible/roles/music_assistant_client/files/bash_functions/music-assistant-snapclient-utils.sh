# function music-assistant-snapclient-logs {
#     journalctl SYSLOG_IDENTIFIER=music-assistant-snapclient "$@"
# }

# function music-assistant-snapclient-status {
#     systemctl --user status music-assistant-snapclient "$@"
# }

# function music-assistant-snapclient-start {
#     systemctl --user start music-assistant-snapclient "$@"
# }

# function music-assistant-snapclient-stop {
#     systemctl --user stop music-assistant-snapclient "$@"
# }

# function music-assistant-snapclient-restart {
#     systemctl --user restart music-assistant-snapclient "$@"
# }

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
