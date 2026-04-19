import subprocess

import logging

logger = logging.getLogger(__name__)

def build_alarm_audio(
    announcement_file: str,
    alarm_file: str,
    output_file: str,
    duration: int = 300
):
    filter_complex = (
        # 1) Force format INCLUDING sample format
        "[0:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo[s0];"
        "[1:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,volume=1.8[s1];"

        # 2) Build ONE cycle: silence → announcement
        "[s0][s1]concat=n=2:v=0:a=1[ann_once];"

        # 3) Loop announcement cycle
        "[ann_once]aloop=loop=-1:size=2e+09[ann];"

        # 4) Prepare alarm
        "[2:a]aformat=sample_fmts=s16:sample_rates=48000:channel_layouts=stereo,"
        "volume=0.5,aloop=loop=-1:size=2e+09[alarm];"

        # 5) Mix
        "[alarm][ann]amix=inputs=2:duration=longest:weights='1 1.5',"

        # ✅ 6) Fade in over 1 second
        f"afade=t=in:st=0:d=1.5,afade=t=out:st={duration-5}:d=5,"

        "adelay=1000|1000"

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

    result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True)
    logger.debug(f"FFmpeg output: {result.stderr}")

def build_announcement_audio(
    announcement_file: str,
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
        "-i", announcement_file,
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
