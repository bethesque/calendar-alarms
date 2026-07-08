#!/usr/bin/env bash
#
# ssh_loop.sh - Run a command over SSH on a fixed list of hosts.
#
# Usage:
#   ./ssh_loop.sh "<command to run>"
#
# Example:
#   ./ssh_loop.sh "uptime"
#   ./ssh_loop.sh "sudo apt update && sudo apt -y upgrade"
#
# Notes:
#   - Assumes SSH key-based auth is set up (no password prompt) and that
#     hostnames resolve via /etc/hosts, DNS, or ~/.ssh/config aliases.
#   - Edit the SSH_USER variable below if you need a specific username,
#     or rely on ~/.ssh/config to set the user per-host instead.

set -uo pipefail

HOSTS=(officepi travcal patpi kaypi)

# Optional: set this if all hosts share a username, e.g. SSH_USER="pi"
SSH_USER=""

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 \"<command to run>\"" >&2
    exit 1
fi

CMD="$*"

for host in "${HOSTS[@]}"; do
    if [[ -n "$SSH_USER" ]]; then
        target="${SSH_USER}@${host}"
    else
        target="$host"
    fi

    echo "=== $host ==="
    if ssh -o ConnectTimeout=5 "$target" -- "$CMD"; then
        echo "--- $host: OK ---"
    else
        echo "--- $host: FAILED (exit code $?) ---" >&2
    fi
    echo
done