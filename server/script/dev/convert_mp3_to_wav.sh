#!/usr/bin/env bash
#
# Convert every .mp3 file in a directory (recursively) to a normalized .wav:
#   - mono (-ac 1)
#   - 44100 Hz (-ar 44100)
#   - 16-bit PCM (-c:a pcm_s16le)
#
# Usage:
#   ./convert_mp3_to_wav.sh /path/to/directory [--delete-mp3]
#
# By default, original .mp3 files are kept alongside the new .wav files.
# Pass --delete-mp3 to remove the source .mp3 after a successful conversion.

set -euo pipefail

SAMPLE_RATE=44100
DELETE_MP3=false

# --- Parse args ---
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <directory> [--delete-mp3]" >&2
    exit 1
fi

TARGET_DIR="$1"
shift || true

for arg in "$@"; do
    case "$arg" in
        --delete-mp3)
            DELETE_MP3=true
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 1
            ;;
    esac
done

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: '$TARGET_DIR' is not a directory" >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Error: ffmpeg not found on PATH" >&2
    exit 1
fi

# --- Find and convert ---
count=0
failed=0

# Use -print0 / read -d '' to safely handle filenames with spaces
while IFS= read -r -d '' mp3_file; do
    dir_name="$(dirname "$mp3_file")"
    base_name="$(basename "$mp3_file" .mp3)"
    wav_file="${dir_name}/${base_name}.wav"

    echo "Converting: $mp3_file -> $wav_file"

    if ffmpeg -y -loglevel error \
        -i "$mp3_file" \
        -ac 1 \
        -ar "$SAMPLE_RATE" \
        -sample_fmt s16 \
        -c:a pcm_s16le \
        "$wav_file"; then

        count=$((count + 1))

        if [ "$DELETE_MP3" = true ]; then
            rm "$mp3_file"
        fi
    else
        echo "  FAILED: $mp3_file" >&2
        failed=$((failed + 1))
    fi
done < <(find "$TARGET_DIR" -type f -iname "*.mp3" -print0)

echo ""
echo "Done. Converted: $count, Failed: $failed"

if [ "$failed" -gt 0 ]; then
    exit 1
fi
