from audio.music_assistant import MusicAssistant, MusicAssistantState
from audio.settings import HomeAssistantSettings
from typing import Protocol
import logging

logger = logging.getLogger(__name__)

class SceneProtocol(Protocol):
    def prepare_for_alarm(self, areas: set[str] | None = None):
        ...

    @staticmethod
    def restore_after_alarm():
        ...

    def prepare_for_announcement(self, areas: set[str] | None = None):
        ...

    def restore_after_announcement(self):
        ...

    def around_announcement(self, announcement_func, areas: set[str] | None = None):
        ...

class NullScene:
    def prepare_for_alarm(self, areas: set[str] | None = None):
        pass

    def restore_after_alarm(self):
        pass

    def prepare_for_announcement(self, areas: set[str] | None = None):
        pass

    def restore_after_announcement(self):
        pass

    def around_announcement(self, announcement_func, areas: set[str] | None = None):
        announcement_func()


class Scene:

    def __init__(self) -> None:
        pass

    def prepare_for_alarm(self, areas: set[str] | None = None):
        try:
            self._build_ma(areas)
            self._save_state()
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
            settings = HomeAssistantSettings()
            ma_state = MusicAssistantState()
            if ma_state.fresh():
                ma = ma_state.load(settings.hass_url, settings.hass_token)
                ma.restore_original_state()
                logger.info("Restored saved Music Assistant state")
                ma_state.clear()
            else:
                logger.info("Not restoring Music Assistant state as the state file is either too old or does not exist")
        except Exception:
            logger.exception(f"Error restoring Music Assistant state")

    def prepare_for_announcement(self, areas: set[str] | None = None):
        try:
            self._build_ma(areas)
            self._save_state()
            if self._ma.playing():
                logger.info(f"Dipping Music Assistant volume in areas {areas}")
                self._ma.dip_volume()
            else:
                logger.info("No Music Assistant players to dip")
        except Exception:
            logger.exception(f"Error dipping Music Assistant players")


    def restore_after_announcement(self):
        self._ma.restore_volume()

    def around_announcement(self, announcement_func, areas: set[str] | None = None):
        self.prepare_for_announcement(areas)
        announcement_func()
        self.restore_after_announcement()

    def _build_ma(self, areas: set[str] | None = None):
        settings = HomeAssistantSettings()
        player_names_to_dip = [player.name for player in settings.players if areas is None or player.area in areas]
        self._ma = MusicAssistant.build_for_players_with_names(
            player_names_to_dip,
            settings.hass_url,
            settings.hass_token,
            settings.announcements
        )
        self._ma.fetch_current_state()

    def _save_state(self):
        try:
            ma_state = MusicAssistantState()
            if self._ma.playing():
                ma_state.save(self._ma)
            else:
                ma_state.clear()
        except Exception:
            logger.exception(f"Exception determining or saving Music Assistant state")
