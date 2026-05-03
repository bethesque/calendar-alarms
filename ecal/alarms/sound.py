import subprocess
import logging
import subprocess
import tempfile
import os

logger = logging.getLogger(__name__)

def build_alarm_audio(
    announcement_file: str,
    alarm_file: str,
    output_file: str,
    duration: int = 300
):

    # Not quite right because we add silence at the beginning and between loops, but it's good enough
    # The overall file will be concatenated at <duration> seconds
    announcement_loops = num_loops(duration, announcement_file)
    alarm_loops = num_loops(duration, alarm_file)

    logger.debug(f"Building alarm audio with announcement_file={announcement_file}, alarm_file={alarm_file}, output_file={output_file}, duration={duration}")
    filter_complex = (
        # 1) Force format INCLUDING sample format
        "[0:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo[s0];"
        "[1:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,volume=1.8[s1];"

        # 2) Build ONE cycle: silence → announcement
        "[s0][s1]concat=n=2:v=0:a=1[ann_once];"

        # 3) Loop announcement cycle
        f"[ann_once]aloop=loop={announcement_loops}:size=2e+09[ann];"

        # 4) Prepare alarm
        "[2:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,"
        f"volume=0.5,aloop=loop={alarm_loops}:size=2e+09[alarm];"

        # 5) Mix
        "[alarm][ann]amix=inputs=2:duration=longest:weights='1 1.2',"

        # ✅ 6) Fade in over 1 second
        f"afade=t=in:st=0:d=1.5,afade=t=out:st={duration-5}:d=5,"

        # 7) Final limiter + trim
        f"alimiter=limit=0.9,atrim=duration={duration}"

    )

    cmd = [
        "ffmpeg",
        "-loglevel", "warning",
        "-f", "lavfi",
        "-t", "5",
        "-i", "anullsrc=r=48000:cl=stereo",
        "-i", announcement_file,
        "-stream_loop", "-1",
        "-i", alarm_file,
        "-filter_complex", filter_complex,

        "-c:a", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",

        "-y",
        output_file,
    ]

    logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")

    result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True)
    logger.debug(f"FFmpeg output: {result.stderr}")

def build_announcement_audio(
    speech_file: str,
    music_file: str,
    output_file: str,
):
    filter_complex = (
        # Announcement (delay + smooth start)
        "[0:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,"
        "volume=1.5,adelay=5000|5000,afade=t=in:st=5:d=1[ann];"

        # Music
        "[1:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,"
        "volume=0.5[music];"

        # Mix
        "[music][ann]amix=inputs=2:duration=longest:weights='1 1.2',"

        # Initial fade-in + limiter
        "afade=t=in:st=0:d=1.5,"
        "alimiter=limit=0.9"
    )

    cmd = [
        "ffmpeg",
        "-loglevel", "warning",
        "-i", speech_file,
        "-i", music_file,
        "-filter_complex", filter_complex,

        "-c:a", "pcm_s16le",
        "-ar", "48000",
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
        """Calculate the number of loops needed to play files for max_length seconds."""
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


def join_mp3s_to_wav(mp3_files: list, output_wav: str):
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        for mp3 in mp3_files:
            f.write(f"file '{os.path.abspath(mp3)}'\n")
        list_file = f.name

    try:
        subprocess.run([
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-vn",
            "-acodec", "pcm_s16le",
            output_wav
        ], check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    finally:
        os.remove(list_file)
