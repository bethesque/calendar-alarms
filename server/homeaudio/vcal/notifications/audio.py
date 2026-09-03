import glob
import random
from homeaudio.audio.sound import build_alarm_audio, join_mp3s_to_wav, build_aggressive_alarm_audio, join_mixed_files_to_wav
from homeaudio.vcal.notifications.text_to_voice import text_to_voice_file
from homeaudio.audio.select_item import select_item_by_date
from homeaudio.vcal.notifications import GENTLE_ALARMS_DIRECTORY, AGGRESSIVE_ALARMS_DIRECTORY, PRE_ANNOUNCEMENT_BELL, OUTPUT_AUDIO_DIRECTORY, SILENCE_HALF_SEC
from homeaudio.audio.settings import AlarmSettings
from homeaudio.housie_talkie.models import SoundEffectSelector


"""
Builds the alarm audio by using TTS to read out the event descriptions, and
mixing in background alarm music.
"""
class AlarmAudio:
    def __init__(self, notification_texts: list[str], alarm_settings: AlarmSettings, base_time):
        self.notification_texts = notification_texts
        self.base_time = base_time
        self.alarm_settings = alarm_settings


    def build_alarm_file(self):
        joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/alarm.wav"
        join_mp3s_to_wav(self._announcement_files_for_events(), joined_announcement_file)

        gentle_audio_file = OUTPUT_AUDIO_DIRECTORY + "/alarm_mixed.wav"

        alarm_file = self._get_alarm_file()

        build_alarm_audio(
            announcement_file=joined_announcement_file,
            alarm_file=alarm_file,
            output_file=gentle_audio_file,
            duration=self.alarm_settings.gentle_alarm_duration
        )

        files_to_loop = [gentle_audio_file]

        if self.alarm_settings.aggressive_alarm_loops > 0:
            loud_noise_warning_file = text_to_voice_file("Warning - an aggressively loud noise is about to be played to get your attention.")

            aggressive_audio_file = OUTPUT_AUDIO_DIRECTORY + "/alarm_aggressive.wav"

            build_aggressive_alarm_audio(
                announcement_file=joined_announcement_file,
                alarm_file=self.get_aggressive_alarm_file(),
                output_file=aggressive_audio_file,
                loops=self.alarm_settings.aggressive_alarm_loops
            )

            files_to_loop.append(loud_noise_warning_file)
            files_to_loop.append(SILENCE_HALF_SEC)
            files_to_loop.append(aggressive_audio_file)

        all_files = files_to_loop * self.alarm_settings.full_loops
        alarm_file = OUTPUT_AUDIO_DIRECTORY + "/alarm.wav"

        join_mixed_files_to_wav(all_files, alarm_file)

        return alarm_file

    def _announcement_files_for_events(self):
        return [text_to_voice_file(text) for text in self.notification_texts]

    def _get_alarm_file(self):
        alarm_files = self._get_alarm_background_files()
        # New alarm every 14 days
        return select_item_by_date(sorted(alarm_files), self.base_time.date(), 14)

    def get_aggressive_alarm_file(self):
        return random.choice(self._get_aggressive_alarm_files())

    def _get_alarm_background_files(self):
        # Get all mp3 files in the ALARMS_DIRECTORY
        alarm_files = glob.glob(f"{GENTLE_ALARMS_DIRECTORY}/*.mp3")
        if not alarm_files:
            raise FileNotFoundError(f"No alarm files found in {GENTLE_ALARMS_DIRECTORY}")
        return alarm_files

    def _get_aggressive_alarm_files(self):
        alarm_files = [
            f for ext in ("*.wav", "*.mp3")
            for f in glob.glob(f"{AGGRESSIVE_ALARMS_DIRECTORY}/{ext}")
        ]
        if not alarm_files:
            raise FileNotFoundError(f"No alarm files found in {AGGRESSIVE_ALARMS_DIRECTORY}")
        return alarm_files


"""
Builds the alarm audio by using TTS to read out the event descriptions, and
mixing in background alarm music.
"""
class AnnouncementAudio:
    def __init__(self, notification_texts: list[str], base_time, sound_effect_selector: SoundEffectSelector):
        self.notification_texts = notification_texts
        self.base_time = base_time
        self.sound_effect_selector = sound_effect_selector

    def build_announcement_file(self):
        joined_announcement_file = OUTPUT_AUDIO_DIRECTORY + "/announcement.wav"
        files = self.preannouncement_files() + self._announcement_files_for_events() + [SILENCE_HALF_SEC]
        join_mp3s_to_wav(files, joined_announcement_file)

        return joined_announcement_file

    def _announcement_files_for_events(self):
        return [text_to_voice_file(text) for text in self.notification_texts]

    def preannouncement_files(self) -> list[str]:
        file = self.sound_effect_selector.get_random_sound_effect_file()
        if file:
            return [PRE_ANNOUNCEMENT_BELL, file]
        else:
            return [PRE_ANNOUNCEMENT_BELL]
