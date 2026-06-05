import asyncio
import json
import os
import time
from pathlib import Path

from vcal.music_assistant import MusicAssistant, MusicAssistantState
from vcal.music_assistant_ws import MusicAssistant as MusicAssistantWS
from vcal.music_assistant_utils import any_players_playing
from vcal.env import CACHE_DIRECTORY, MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN, PLAYERS, DIP_TARGET_VOLUME, DIP_VOLUME
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

    def around_announcement(self, announcement_func):
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

    def around_announcement(self, announcement_func):
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

    def around_announcement(self, announcement_func):
        pass


class AsyncScene:
    def __init__(self) -> None:
        pass

    async def save(self):
        pass

    async def prepare_for_alarm_async(self):
        try:
            async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                if ma.playing():
                    SceneStateFile().save(ma.fetch_current_state())
                    await ma.fade_down_and_pause(duration_seconds=3, intervals=20)
        except Exception:
            logger.exception(f"Error pausing Music Assistant players")


    @staticmethod
    async def restore_after_alarm():
        try:
            state_file = SceneStateFile()
            if state_file.fresh():
                state = SceneStateFile().load()
                if any(state):
                    async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                        await ma.resume_and_fade_up(state, duration_seconds=5, intervals=20)
            else:
                logger.info("Not restoring Music Assistant state as the state file is either too old or does not exist")
        except Exception:
            logger.exception(f"Error restoring Music Assistant players")

    async def prepare_for_announcement(self):
        music_assistant_available = False
        try:
            async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                music_assistant_available = True
                if ma.playing():
                    SceneStateFile().save(state = ma.fetch_current_state())
                    await ma.fade_down(target_volume=DIP_VOLUME, duration_seconds=3, intervals=15)
                else:
                    SceneStateFile().clear()
                    logger.info("No Music Assistant players to dip")
        except Exception as e:
            if not music_assistant_available:
                 logger.info(f"Music Assistant is not available at {MUSIC_ASSISTANT_URL} ({type(e).__name__} - {e}) — proceeding with announcement without dipping volume")
            else:
                logger.exception(f"Error dipping volume of Music Assistant players")

    async def restore_after_announcement(self):
        try:
            state_file = SceneStateFile()
            if state_file.fresh():
                state = state_file.load()
                if any(state):
                    async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                        await ma.fade_up(state, duration_seconds=3, intervals=20)
        except Exception:
            logger.exception(f"Error restoring state of Music Assistant players")

    async def around_announcement(self, announcement_func):
        music_assistant_available = False
        state = []
        try:
            async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                music_assistant_available = True
                if ma.playing():
                    state = ma.fetch_current_state()
                    try:
                        await ma.fade_down(target_volume=DIP_VOLUME, duration_seconds=2, intervals=10)
                    except Exception:
                        logger.exception(f"Error dipping volume of Music Assistant players")
                else:
                    logger.info("No Music Assistant players to dip")

                announcement_func()

                if any(state):
                    try:
                        await ma.fade_up(state, duration_seconds=4, intervals=20)
                    except Exception:
                        logger.exception(f"Error restoring volume of Music Assistant players")

        except Exception as e:
            if not music_assistant_available:
                 logger.info(f"Music Assistant is not available at {MUSIC_ASSISTANT_URL} ({type(e).__name__} - {e}) — proceeding with announcement without dipping volume")
                 announcement_func()
            else:
                logger.exception(f"Error dipping volume of Music Assistant players")


class SceneStateFile:
    MUSIC_ASSISTANT_STATE_FILE = CACHE_DIRECTORY + "/music_assistant_state_2.json"

    def __init__(self, path: str = MUSIC_ASSISTANT_STATE_FILE) -> None:
        self.path = path

    def save(self, state):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(state, f)

    def load(self):
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except Exception:
            logger.exception("Error loading Music Assistant state from file")
            return {}

    def clear(self):
        try:
            Path(self.path).unlink(missing_ok=True)
        except Exception:
            logger.exception("Error clearing Music Assistant state from file")

    def fresh(self, max_age_mins=5) -> bool:
        max_age_seconds = max_age_mins * 60
        try:
            mtime = os.path.getmtime(self.path)
        except FileNotFoundError:
            return False
        return (time.time() - mtime) < max_age_seconds


class Scene2:
    _state: dict

    def __init__(self) -> None:
        pass

    def save(self):
        pass

    def prepare_for_alarm(self):
        if any_players_playing(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN):
            asyncio.run(AsyncScene().prepare_for_alarm_async())
        else:
            SceneStateFile().clear()
            logger.info("No Music Assistant players to pause")


    # This method gets called from the HTTP endpoint, so has no shared state with the other methods
    @staticmethod
    def restore_after_alarm():
        asyncio.run(AsyncScene.restore_after_alarm())

    def prepare_for_announcement(self):
        if any_players_playing(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN):
            asyncio.run(AsyncScene().prepare_for_alarm_async())
        else:
            SceneStateFile().clear()
            logger.info("No Music Assistant players to fade down")

    def restore_after_announcement(self):
        asyncio.run(AsyncScene().restore_after_announcement())

    def around_announcement(self, announcement_func):
        if any_players_playing(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN):
            asyncio.run(AsyncScene().around_announcement(announcement_func))
        else:
            logger.info("No Music Assistant players to dip for announcement")
            announcement_func()

