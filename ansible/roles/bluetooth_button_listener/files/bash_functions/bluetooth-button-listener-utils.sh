function bluetooth-button-listener-status {
    systemctl --user status bluetooth-button-listener
}

function bluetooth-button-listener-start {
    systemctl --user start bluetooth-button-listener
}

function bluetooth-button-listener-restart {
    systemctl --user restart bluetooth-button-listener
}

function bluetooth-button-listener-stop {
    systemctl --user stop bluetooth-button-listener
}

function bluetooth-button-listener-logs {
    journalctl SYSLOG_IDENTIFIER=bluetooth-button-listener "$@"
}
