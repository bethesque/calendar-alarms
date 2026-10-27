import subprocess
import logging
import subprocess
import tempfile
import os
from homeaudio.vcal.event_notifications import SAMPLE_RATE, AUDIO_CACHE_DIR

logger = logging.getLogger(__name__)

import os
import subprocess

SPEECH_GAIN = 0.98  # was volume=1.8 * amix weight 1.2/2.2
ALARM_GAIN = 0.23   # was volume=0.5 * amix weight 1/2.2


def _normalized_copy(src: str) -> str:
    """Convert src to mono s16 WAV at SAMPLE_RATE once, and reuse it on later runs."""
    parent = os.path.basename(os.path.dirname(os.path.abspath(src)))
    stem = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(AUDIO_CACHE_DIR, parent, f"{stem}.{SAMPLE_RATE}.mono.wav")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return dst

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".tmp"
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "warning", "-i", src,
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le",
            "-f", "wav", "-y", tmp,
        ],
        check=True,
    )
    os.replace(tmp, dst)
    return dst


def build_alarm_audio(
    speech_file: str,
    alarm_file: str,
    output_file: str,
    duration: int = 300,
    use_limiter: bool = False,
):
    # Pre-converted once; later runs skip decoding/resampling of the alarm entirely
    alarm_file = _normalized_copy(alarm_file)

    # Not quite right because we add silence at the beginning and between loops, but it's good enough
    announcement_loops = num_loops(duration, speech_file)

    logger.debug(
        f"Building alarm audio with announcement_file={speech_file}, "
        f"alarm_file={alarm_file}, output_file={output_file}, duration={duration}"
    )

    fmt = f"aformat=sample_fmts=s16:sample_rates={SAMPLE_RATE}:channel_layouts=mono"

    filter_complex = (
        # 1) Force format on silence + speech (alarm is already mono s16 at SAMPLE_RATE)
        f"[0:a]{fmt}[s0];"
        f"[1:a]{fmt},volume={SPEECH_GAIN}[s1];"

        # 2) One cycle: silence -> announcement, then loop it
        "[s0][s1]concat=n=2:v=0:a=1[ann_once];"
        f"[ann_once]aloop=loop={announcement_loops}:size=2e+09[ann];"

        # 3) Alarm: looped by -stream_loop on the input, so just apply gain
        f"[2:a]volume={ALARM_GAIN}[alarm];"

        # 4) Mix with fixed gains (no auto-normalisation), then fades
        "[alarm][ann]amix=inputs=2:duration=longest:normalize=0,"
        f"afade=t=in:st=0:d=4,afade=t=out:st={duration - 2}:d=2"

        # 5) Optional limiter
        + (",alimiter=limit=0.9" if use_limiter else "")
    )

    cmd = [
        "ffmpeg",
        "-loglevel", "warning",
        "-f", "lavfi",
        "-t", "5",  # 5 seconds of silence before and between announcements
        "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
        "-i", speech_file,
        "-stream_loop", "-1",
        "-i", alarm_file,
        "-filter_complex", filter_complex,

        "-c:a", "pcm_s16le",
        "-ar", f"{SAMPLE_RATE}",
        "-ac", "2",

        "-t", str(duration),  # stop reading once we have enough (replaces atrim)
        "-y",
        output_file,
    ]

    logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    logger.debug(f"FFmpeg output: {result.stderr}")

import os
import subprocess

def build_aggressive_alarm_audio(
    announcement_file: str,
    alarm_file: str,
    output_file: str,
    loops: int,
    timeout: float = 300,
) -> None:
    """
    Write `loops` repetitions of (alarm, announcement) to output_file
    as mono 16-bit PCM WAV at SAMPLE_RATE. The file is written atomically.
    """
    if loops < 1:
        raise ValueError(f"loops must be >= 1, got {loops}")
    for path in (announcement_file, alarm_file):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

    fmt = f"aformat=sample_fmts=s16:sample_rates={SAMPLE_RATE}:channel_layouts=mono"
    filter_complex = (
        f"[0:a]{fmt}[alarm];"
        f"[1:a]{fmt}[ann];"
        # One cycle: alarm -> announcement, then repeat it (loop=N plays N+1 times)
        "[alarm][ann]concat=n=2:v=0:a=1,"
        f"aloop=loop={loops - 1}:size=2e+09[out]"
    )

    tmp_path = f"{output_file}.tmp"
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-loglevel", "warning",
        "-i", alarm_file,
        "-i", announcement_file,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "-f", "wav",
        tmp_path,
    ]

    logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        logger.debug(f"FFmpeg output: {result.stderr}")

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit code {result.returncode}):\n{result.stderr}"
            )
        os.replace(tmp_path, output_file)
    finally:
        # Clean up on failure or timeout; no-op after a successful replace
        if os.path.exists(tmp_path):
            os.remove(tmp_path)



def mix_announcement_audio(
    speech_file: str,
    music_file: str,
    output_file: str,
):

    delay = 5
    fade_duration = 3
    speech_file_length = track_length(speech_file)
    full_duration_seconds = speech_file_length + delay + fade_duration
    music_loops = num_loops(full_duration_seconds, music_file)

    fade_start = full_duration_seconds - fade_duration
    size=track_length(music_file) * SAMPLE_RATE

    filter_complex = (
        # Announcement (delay + smooth start)
        f"[0:a]aformat=sample_fmts=s16:sample_rates={SAMPLE_RATE}:channel_layouts=mono,"
        f"volume=1.5,adelay={delay * 1000}|{delay * 1000}[ann];"

        # Music
        f"[1:a]aformat=sample_fmts=s16:sample_rates={SAMPLE_RATE}:channel_layouts=mono,volume=0.5,"
        f"aloop=loop={music_loops}:size={size},"
        "asetpts=N/SR/TB,"
        f"atrim=start=0:end={full_duration_seconds:.2f},"
        "afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={fade_start:.2f}:d={fade_duration}[music];"

        # Mix
        f"[music][ann]amix=inputs=2:weights='1 1.2',"

        # Initial fade-in + limiter
        "alimiter=limit=0.9"
    )

    cmd = [
        "ffmpeg",
        "-loglevel", "warning",
        "-i", speech_file,
        "-i", music_file,
        "-filter_complex", filter_complex,

        "-c:a", "pcm_s16le",
        "-ar", f"{SAMPLE_RATE}",
        "-ac", "2",

        "-y",
        output_file,
    ]

    result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True)
    logger.debug(f"FFmpeg output: {result.stderr}")


def num_loops(max_length: float, *file_paths: str) -> int:
    """Calculate the number of loops needed to play files for max_length seconds, rounding DOWN so that it is less than the max."""
    total_length = sum(track_length(fp) for fp in file_paths)
    return max(1, int(max_length // total_length))

"""
Length of the audio file in seconds.
"""
def track_length(path: str)  -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"Failed to get duration: {e}")

def join_mixed_files_to_wav(files: list, output_wav: str):
    """
    Join an arbitrary list of audio files (mixed formats/codecs allowed,
    e.g. mp3, m4a, wav) into a single WAV file using ffmpeg.

    :param files: list of input file paths, in the order they should be joined
    :param output_wav: path to the output .wav file
    """
    if not files:
        raise ValueError("files list must not be empty")

    # Build -i flags for each input
    input_args = []
    for f in files:
        input_args.extend(["-i", f])

    # Normalize each input to mono first: [0:a]aformat=...[a0];[1:a]aformat=...[a1];...
    normalize_parts = [
        f"[{i}:a]aformat=channel_layouts=mono[a{i}]" for i in range(len(files))
    ]
    normalize = ";".join(normalize_parts) + ";"

    # Concat using the normalized labels instead of raw [i:a]
    stream_labels = "".join(f"[a{i}]" for i in range(len(files)))
    filter_complex = f"{normalize}{stream_labels}concat=n={len(files)}:v=0:a=1[out]"

    cmd = [
        "ffmpeg",
        "-y",  # overwrite output if it exists
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ar", f"{SAMPLE_RATE}",
        "-ac", "1",
        output_wav,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit code {result.returncode}):\n{result.stderr}"
        )

    return output_wav



def change_speed(input_file: str, output_file: str, speed: float = 1.1) -> str:
    """Speed up speech by `speed` without changing pitch."""
    tmp_path = f"{output_file}.tmp"
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-loglevel", "warning",
        "-i", input_file,
        "-filter:a", f"atempo={speed}",
        "-c:a", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "-f", "wav",
        tmp_path,
    ]

    logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit code {result.returncode}):\n{result.stderr}"
            )
        os.replace(tmp_path, output_file)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return output_file
