from pathlib import Path
from vcal.settings import HousieTalkieSettings
from housie_talkie.voice_ffmpeg import normalize_audio
from housie_talkie.core import play_voice_announcement as og_play_audio_file_as_announcement, VoiceAnnouncementRequest
from vcal.notifications import OUTPUT_AUDIO_DIRECTORY

def play_audio_file_as_announcement(request: VoiceAnnouncementRequest):
    normalized_audio_file = _normalize_audio_file_to_match_tts_volume(request.audio_file)
    normalized_request = VoiceAnnouncementRequest(
        audio_file=normalized_audio_file,
        scene=request.scene,
        sound_effect=request.sound_effect,
        player_names=request.player_names
    )

    og_play_audio_file_as_announcement(normalized_request)

def _normalize_audio_file_to_match_tts_volume(audio_file):
    housie_talkie_settings = HousieTalkieSettings()
    normalized_audio_file = _normalize_audio_file_path(audio_file)
    normalize_audio(
        audio_file,
        normalized_audio_file,
        housie_talkie_settings.target_integrated_loudness,
        housie_talkie_settings.target_true_peak,
        housie_talkie_settings.target_loudness_range)
    return normalized_audio_file

def _normalize_audio_file_path(audio_file):
    path = Path(audio_file)
    return OUTPUT_AUDIO_DIRECTORY + "/" + path.stem + "_normalized" + path.suffix

