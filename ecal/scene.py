from ecal.music_assistant import MusicAssistant, MusicAssistantState
from ecal.env import CACHE_DIRECTORY, PLAYERS

import logging

logger = logging.getLogger(__name__)

class Scene:

    @staticmethod
    def prepare():
        try:
            logger.info("Pausing Music Assistant players (if any)...")
            ma = MusicAssistant.build_for_players_with_names(PLAYERS)
            ma.fetch_current_state()
            MusicAssistantState.save(ma)
            ma.fade_out_and_pause()
        except Exception:
            logger.exception(f"Error pausing Music Assistant players")

    @staticmethod
    def restore():
        try:
            if MusicAssistantState.fresh():
                ma = MusicAssistantState.load()
                ma.restore_original_state()
                logger.info("Restored saved Music Assistant state")
                MusicAssistantState.clear()
            else:
                logger.info("Not restoring Music Assistant state as the state file is either too old or does not exist")
        except Exception:
            logger.exception(f"Error restoring Music Assistant state")

