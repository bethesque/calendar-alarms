from pathlib import Path

AUDIO_DIRECTORY = Path("audio_resources").absolute()
GENTLE_ALARMS_DIRECTORY = Path(f"{AUDIO_DIRECTORY}/alarms_gentle").absolute()
AGGRESSIVE_ALARMS_DIRECTORY = Path(f"{AUDIO_DIRECTORY}/alarms_aggressive").absolute()
BACKGROUND_MUSIC_DIRECTORY = Path(f"{AUDIO_DIRECTORY}/background_music").absolute()
OUTPUT_AUDIO_DIRECTORY = Path("/tmp") # Do not resolve this one or Mac gets confused
SAMPLE_RATE = 44100

# ffmpeg -f lavfi -i anullsrc=channel_layout=mono:sample_rate=44100 -t 0.25 -q:a 9 -acodec libmp3lame silence.mp3

SILENCE_HALF_SEC = f"{AUDIO_DIRECTORY}/silence_500ms.mp3"
SILENCE_QUARTER_SEC = f"{AUDIO_DIRECTORY}/silence_250ms.mp3"
PRE_ANNOUNCEMENT_BELL = f"{AUDIO_DIRECTORY}/preannounce_4.mp3"
POST_ANNOUNCEMENT_SILENCE = SILENCE_QUARTER_SEC
