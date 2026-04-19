#!/bin/bash

echo "This works"
echo '{ "command": ["loadfile", "/home/beth/calendar-alarms/alarm_mix.wav"] }'  | socat - /tmp/mpv_mixed.sock
sleep 1

echo '{ "command": ["get_property", "idle-active"] }' | socat - /tmp/mpv_mixed.sock

sleep 5
echo '{ "command": ["stop"] }' | socat - /tmp/mpv_mixed.sock
echo '{ "command": ["get_property", "idle-active"] }' | socat - /tmp/mpv_mixed.sock

echo "This does nothing"
echo '{ "command": ["playlist_clear"] }'  | socat - /tmp/mpv_mixed.sock
echo '{ "command": ["loadfile", "/home/beth/calendar-alarms/alarm_mix.wav", "replace"] }'  | socat - /tmp/mpv_mixed.sock
