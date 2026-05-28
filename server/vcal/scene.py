import asyncio
import json
import os
import time
from pathlib import Path

from vcal.music_assistant import MusicAssistant, MusicAssistantState
from vcal.music_assistant_ws import MusicAssistant as MusicAssistantWS
from vcal.env import CACHE_DIRECTORY, MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN, PLAYERS, DIP_TARGET_VOLUME
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
                    state = ma.fetch_current_state()
                    SceneState(state).save()
                    await ma.fade_down(target_volume=0, duration_seconds=3, intervals=20)
                    await ma.pause()
                else:
                    logger.info("No Music Assistant players to pause")
        except Exception:
            logger.exception(f"Error pausing Music Assistant players")


    @staticmethod
    async def restore_after_alarm():
        try:
            state = SceneState().load()
            if any(state):
                async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                    player_ids = [p["player_id"] for p in state]
                    await ma.play(player_ids)
                    time.sleep(2) # wait for buffers to fill so that players don't immediately pause again when we set volume back up
                    await ma.fade_up_restore(state, duration_seconds=5, intervals=20)
        except Exception:
            logger.exception(f"Error restoring Music Assistant players")

    async def prepare_for_announcement(self):
        try:
            async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                if ma.playing():
                    state = ma.fetch_current_state()
                    SceneState(state).save()
                    await ma.fade_down(target_volume=DIP_TARGET_VOLUME, duration_seconds=3, intervals=15)
                else:
                    logger.info("No Music Assistant players to dip")
        except Exception:
            logger.exception(f"Error dipping volume of Music Assistant players")

    async def restore_after_announcement(self, state):
        try:
            async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                await ma.fade_up_restore(state, duration_seconds=3, intervals=20)
        except Exception:
            logger.exception(f"Error dipping volume of Music Assistant players")

    async def around_announcement(self, announcement_func):
        music_assistant_available = False
        state = []
        try:
            async with MusicAssistantWS(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
                music_assistant_available = True
                if ma.playing():
                    state = ma.fetch_current_state()
                    try:
                        await ma.fade_down(target_volume=DIP_TARGET_VOLUME, duration_seconds=3, intervals=15)
                    except Exception:
                        logger.exception(f"Error dipping volume of Music Assistant players")
                else:
                    logger.info("No Music Assistant players to dip")

                announcement_func()

                if any(state):
                    try:
                        await ma.fade_up_restore(state, duration_seconds=5, intervals=20)
                    except Exception:
                        logger.exception(f"Error restoring volume of Music Assistant players")

        except Exception as e:
            if not music_assistant_available:
                 logger.info(f"Music Assistant is not available at {MUSIC_ASSISTANT_URL} ({type(e).__name__} - {e}) — proceeding with announcement without dipping volume")
                 announcement_func()
            else:
                logger.exception(f"Error dipping volume of Music Assistant players")


class SceneState:
    MUSIC_ASSISTANT_STATE_FILE = CACHE_DIRECTORY + "/music_assistant_state_2.json"

    def __init__(self, music_assistant_state: dict | None = None) -> None:
        self.state = music_assistant_state or {}

    def save(self):
        print("Saving Music Assistant state:", self.state)
        os.makedirs(os.path.dirname(self.MUSIC_ASSISTANT_STATE_FILE), exist_ok=True)
        with open(self.MUSIC_ASSISTANT_STATE_FILE, "w") as f:
            json.dump(self.state, f)

    def load(self):
        try:
            with open(self.MUSIC_ASSISTANT_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            logger.exception("Error loading Music Assistant state from file")
            return {}

    @staticmethod
    def clear():
        try:
            # delete the state file to clear it
            Path(SceneState.MUSIC_ASSISTANT_STATE_FILE).unlink(missing_ok=True)
        except Exception:
            logger.exception("Error clearing Music Assistant state from file")

    @staticmethod
    def fresh( max_age_mins = 5) -> bool:
        max_age_seconds = max_age_mins * 60
        try:
            mtime = os.path.getmtime(SceneState.MUSIC_ASSISTANT_STATE_FILE)
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
        asyncio.run(AsyncScene().prepare_for_alarm_async())

    # This method gets called from the HTTP endpoint, so has no shared state with the other methods
    @staticmethod
    def restore_after_alarm():
        if SceneState.fresh():
            asyncio.run(AsyncScene.restore_after_alarm())
        else:
            logger.info("Not restoring Music Assistant state as the state file is either too old or does not exist")

    def prepare_for_announcement(self):
        asyncio.run(AsyncScene().prepare_for_announcement())

    def restore_after_announcement(self):
        if SceneState.fresh():
            state = SceneState().load()
            if any(state):
                asyncio.run(AsyncScene().restore_after_announcement(state))

    def around_announcement(self, announcement_func):
        asyncio.run(AsyncScene().around_announcement(announcement_func))

