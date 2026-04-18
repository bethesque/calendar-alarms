import subprocess

def build_alarm(announcement, alarm, output, duration=300):
    subprocess.run([
        "ffmpeg",
        "-f", "lavfi",
        "-t", "5",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-i", announcement,
        "-stream_loop", "-1",
        "-i", alarm,
        "-filter_complex",

        # 1) Take input 0 (silence) + input 1 (announcement)
        #    Concatenate them into a single audio stream
        #    Then loop that combined stream forever and label it [ann]
        "[0:a][1:a]concat=n=2:v=0:a=1,"        # join silence + announcement
        "aloop=loop=-1:size=2e+09[ann];"       # loop it infinitely → [ann]

        # 2) Take input 2 (alarm audio)
        #    Lower its volume to 60% so it doesn't overpower speech
        #    Loop it forever and label it [alarm]
        "[2:a]volume=0.6,"                     # reduce alarm loudness
        "aloop=loop=-1:size=2e+09[alarm];"     # loop alarm infinitely → [alarm]

        # 3) Mix both streams together:
        #    - alarm (background)
        #    - announcement loop (foreground)
        #    Output continues as long as the longest stream runs
        "[alarm][ann]amix=inputs=2:duration=longest,"
        f"atrim=duration={duration}",
        "-c:a", "flac",
        "-y",
        output
    ], check=True)


import subprocess

import subprocess


import subprocess


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

    subprocess.run(cmd, check=True)


#build_alarm("audio/test_announcement.mp3", "audio/alarm.mp3", "output.flac", duration=300)

build_alarm_audio("audio/test_announcement.mp3", "audio/alarm.mp3", "bethtest-announce-and-music-fade-in.wav", duration=300)