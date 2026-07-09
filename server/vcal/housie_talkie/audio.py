"""
Two-pass loudness normalization for HousieTalkie voice recordings.

Matches recorded voice messages to Google TTS's measured loudness profile
(-19.0 LUFS, -1.5 dBTP true peak ceiling) using ffmpeg's loudnorm filter
in two-pass mode for accurate, consistent results.

Re-encodes the output using the SAME codec, bitrate, channel count, and
sample rate as the source file, so normalization changes loudness only --
not the audio format.

Requires: ffmpeg and ffprobe installed and available on PATH.
"""

import json
import subprocess
from pathlib import Path

# Target values derived from measuring 3 Google TTS samples (see analysis)
# ffmpeg -i tts.mp3 -filter:a loudnorm=print_format=summary -f null -
TARGET_I = -19.0    # Integrated loudness (LUFS)
TARGET_TP = -1.5    # True peak ceiling (dBTP)
TARGET_LRA = 1.0    # Loudness range (LU) - flat, TTS-like dynamics


def _run_ffmpeg(args):
    """Run an ffmpeg command and return combined stdout+stderr (ffmpeg logs to stderr)."""
    result = subprocess.run(
        ["ffmpeg", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + result.stderr)
    return result.stderr  # loudnorm's JSON output is printed to stderr


def _measure_loudness(input_path, target_i, target_tp, target_lra):
    """Pass 1: analyze the file and return the measured loudnorm stats."""
    filter_str = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json"
    )
    output = _run_ffmpeg([
        "-i", input_path,
        "-filter:a", filter_str,
        "-f", "null",
        "-",
    ])

    # loudnorm prints a JSON block; extract it (it's the last {...} in the output)
    json_start = output.rfind("{")
    json_end = output.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        raise RuntimeError("Could not find loudnorm JSON output:\n" + output)

    return json.loads(output[json_start:json_end])


def _get_source_audio_info(input_path):
    """Use ffprobe to read the source file's codec, bitrate, channels, sample rate."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,bit_rate,channels,sample_rate",
            "-of", "json",
            input_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("ffprobe failed:\n" + result.stderr)

    info = json.loads(result.stdout)["streams"][0]
    return {
        "codec_name": info.get("codec_name"),
        "bit_rate": int(info["bit_rate"]) if "bit_rate" in info else None,
        "channels": info.get("channels"),
        "sample_rate": info.get("sample_rate"),
    }


def normalize_audio(
    input_path,
    output_path,
    target_i=TARGET_I,
    target_tp=TARGET_TP,
    target_lra=TARGET_LRA,
):
    """
    Normalize a voice recording to match Google TTS loudness using two-pass loudnorm.

    Re-encodes using the same codec, bitrate, channel count, and sample rate as
    the source file (read via ffprobe) -- so the output format matches the input
    exactly; only the loudness changes.

    Args:
        input_path: Path to the source audio file (e.g. .m4a from MediaRecorder).
        output_path: Path to write the normalized output file. Should use the same
            container/extension as the source (e.g. .m4a) to match the codec.
        target_i: Target integrated loudness in LUFS.
        target_tp: Target true peak ceiling in dBTP.
        target_lra: Target loudness range in LU.

    Returns:
        Dict with 'measured' (pass-1 loudnorm stats) and 'source_info' (codec/
        bitrate/channels/sample_rate read from the original file).
    """
    input_path = str(input_path)
    output_path = str(output_path)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Read source format so the output matches it exactly
    source_info = _get_source_audio_info(input_path)

    codec = source_info["codec_name"] or "aac"
    bitrate = f"{source_info['bit_rate'] // 1000}k" if source_info["bit_rate"] else "128k"
    channels = source_info["channels"] or 1
    sample_rate = source_info["sample_rate"] or "44100"

    # Pass 1: measure
    stats = _measure_loudness(input_path, target_i, target_tp, target_lra)

    # Pass 2: apply using the real measured values (linear=true for accurate correction)
    filter_str = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
        f"measured_I={stats['input_i']}:"
        f"measured_TP={stats['input_tp']}:"
        f"measured_LRA={stats['input_lra']}:"
        f"measured_thresh={stats['input_thresh']}:"
        f"offset={stats['target_offset']}:"
        f"linear=true:print_format=summary,"
        f"alimiter=limit=0.95"
    )

    _run_ffmpeg([
        "-i", input_path,
        "-filter:a", filter_str,
        "-c:a", codec,
        "-b:a", bitrate,
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "-y",  # overwrite output if it exists
        output_path,
    ])

    return {"measured": stats, "source_info": source_info}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python normalize_audio.py <input_file> <output_file>")
        sys.exit(1)

    src, dst = sys.argv[1], sys.argv[2]
    print(f"Normalizing {src} -> {dst} ...")
    result = normalize_audio(src, dst)
    m = result["measured"]
    s = result["source_info"]
    print(f"Source: {s['codec_name']}, {s['bit_rate']} bps, "
          f"{s['channels']}ch, {s['sample_rate']}Hz")
    print(f"Measured input loudness: {m['input_i']} LUFS "
          f"(true peak {m['input_tp']} dBTP)")