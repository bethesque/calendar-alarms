
AUDIO_DIRECTORY = "audio_resources"
GENTLE_ALARMS_DIRECTORY = f"{AUDIO_DIRECTORY}/alarms_gentle"
AGGRESSIVE_ALARMS_DIRECTORY = f"{AUDIO_DIRECTORY}/alarms_aggressive"
BACKGROUND_MUSIC_DIRECTORY = f"{AUDIO_DIRECTORY}/background_music"
OUTPUT_AUDIO_DIRECTORY = "/tmp"
SAMPLE_RATE = 44100

# ffmpeg -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t 0.25 -q:a 9 -acodec libmp3lame silence.mp3

SILENCE_HALF_SEC = f"{AUDIO_DIRECTORY}/silence_500ms.mp3"
SILENCE_QUARTER_SEC = f"{AUDIO_DIRECTORY}/silence_250ms.mp3"
PRE_ANNOUNCEMENT_BELL = f"{AUDIO_DIRECTORY}/preannounce_4.mp3"
