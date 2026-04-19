#!/bin/bash
# Run from project root. This script is intended to be run from a cron job to play the morning announcements.

set -Eeuo pipefail

echo "Morning announcements at $(date)"

export PATH="/home/$(id -un)/.local/bin:${PATH}"

source .env

./script/connect_bluetooth_speaker.sh


