from ecal.music_assistant import MusicAssistant, MusicAssistantState
from ecal.env import CACHE_DIRECTORY, PLAYERS

import logging

logger = logging.getLogger(__name__)

class Scene:

    @staticmethod
    def prepare():
        try:
            ma_state = MusicAssistantState()
            ma = MusicAssistant.build_for_players_with_names(PLAYERS)
            ma.fetch_current_state()
            if ma.playing():
                logger.info("Pausing Music Assistant players...")
                ma_state.save(ma)
                ma.fade_out_and_pause()
            else:
                logger.info("No Music Assistant players to pause")
                ma_state.clear()
        except Exception:
            logger.exception(f"Error pausing Music Assistant players")

    @staticmethod
    def restore():
        try:
            ma_state = MusicAssistantState()
            if ma_state.fresh():
                ma = ma_state.load()
                ma.restore_original_state()
                logger.info("Restored saved Music Assistant state")
                ma_state.clear()
            else:
                logger.info("Not restoring Music Assistant state as the state file is either too old or does not exist")
        except Exception:
            logger.exception(f"Error restoring Music Assistant state")

