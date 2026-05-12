#!/bin/bash

set -Eeuo pipefail

: "${BLUETOOTH_SPEAKER_MAC:?BLUETOOTH_SPEAKER_MAC environment variable is required}"

MAX_RETRIES=5

echo "=== Bluetooth Audio Script Start ==="

# --- ENV FIX (required for cron/systemd) ---
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

# --- FUNCTIONS ---

is_connected() {
    bluetoothctl info "$BLUETOOTH_SPEAKER_MAC" | grep -q "Connected: yes"
}

get_bt_sink() {
    pactl list short sinks | grep bluez | awk '{print $2}' | head -n1
}

is_audio_ready() {
    pactl list short sinks | grep -q bluez
}

connect_bt() {
    echo "Connecting to Bluetooth device..."
    printf "connect %s\nquit\n" "$BLUETOOTH_SPEAKER_MAC" | bluetoothctl
}

# --- MAIN LOGIC ---

echo "Checking Bluetooth status for speaker ${BLUETOOTH_SPEAKER_MAC}..."

if is_connected && is_audio_ready; then
    echo "Bluetooth already connected and audio ready ✅"
else
    echo "Bluetooth not ready, attempting to fix..."

    for ((i=1; i<=MAX_RETRIES; i++)); do
        echo "Attempt $i..."

        if ! is_connected; then
            connect_bt
        fi

        sleep 3

        if is_audio_ready; then
            echo "Audio is ready ✅"
            break
        fi
    done
fi

# --- FINAL CHECK ---

SINK=$(get_bt_sink)

if [ -z "$SINK" ]; then
    echo "ERROR: No Bluetooth audio sink found ❌"
    exit 1
fi

echo "Using sink: $SINK"
pactl set-default-sink "$SINK"
