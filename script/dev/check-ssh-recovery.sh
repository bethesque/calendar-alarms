#!/bin/bash
# check-ssh-recovery.sh
# Run on your Mac. Polls travcal until SSH becomes reachable again, then alerts you.

HOST="travcal"       # change to travcal's IP if .local resolution is part of the problem
PORT=22
INTERVAL=30           # seconds between checks

echo "Watching for SSH on $HOST:$PORT to come back... (checking every ${INTERVAL}s)"

while true; do
    if nc -z -w 5 "$HOST" "$PORT" 2>/dev/null; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') — SSH is back up on $HOST"
        say "SSH is back up on travcal" 2>/dev/null   # macOS voice alert
        osascript -e 'display notification "SSH is back up" with title "travcal"' 2>/dev/null
        break
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') — still down"
    fi
    sleep "$INTERVAL"
done

