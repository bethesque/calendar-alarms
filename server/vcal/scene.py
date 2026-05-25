from vcal.music_assistant import MusicAssistant, MusicAssistantState
from vcal.env import PLAYERS
from typing import Protocol
import logging

logger = logging.getLogger(__name__)

class SceneProtocol(Protocol):
    def save(self):
        ...

    def prepare_for_alarm(self):
        ...

    @staticmethod
    def restore_after_alarm():
        ...

    def prepare_for_announcement(self):
        ...

    def restore_after_announcement(self):
        ...

class NullScene:
    def save(self):
        pass

    def prepare_for_alarm(self):
        pass

    def restore_after_alarm(self):
        pass

    def prepare_for_announcement(self):
        pass

    def restore_after_announcement(self):
        pass


class Scene:

    def __init__(self) -> None:
        pass

    def save(self):
        try:
            ma_state = MusicAssistantState()
            self._ma = MusicAssistant.build_for_players_with_names(PLAYERS)
            self._ma.fetch_current_state()
            if self._ma.playing():
                ma_state.save(self._ma)
            else:
                ma_state.clear()
        except Exception:
            logger.exception(f"Exception determining or saving Music Assistant state")

    def prepare_for_alarm(self):
        try:
            if self._ma.playing():
                logger.info("Pausing Music Assistant players...")
                self._ma.fade_out_and_pause()
            else:
                logger.info("No Music Assistant players to pause")
        except Exception:
            logger.exception(f"Error pausing Music Assistant players")


    # This method gets called from the HTTP endpoint, so has no shared state with the other methods
    @staticmethod
    def restore_after_alarm():
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

    def prepare_for_announcement(self):
        try:
            if self._ma.playing():
                logger.info("Dipping Music Assistant volume...")
                self._ma.dip_volume()
            else:
                logger.info("No Music Assistant players to dip")
        except Exception:
            logger.exception(f"Error dipping Music Assistant players")


    def restore_after_announcement(self):
        self._ma.restore_volume()
