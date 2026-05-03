import requests
import time
import logging
import os
import json
from pathlib import Path
from typing import List, Tuple
import logging
from dataclasses import dataclass


from ecal.env import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN, CACHE_DIRECTORY

logger = logging.getLogger(__name__)

MUSIC_ASSISTANT_STATE_FILE = CACHE_DIRECTORY + "/music_assistant_state.json"

@dataclass
class PlayerState:
    state: dict

    def get_volume(self) -> float:
        return float(self.state.get("attributes", {}).get("volume_level", 0.0))

    def playing(self) -> bool:
        return self.state.get("state", "") in ["playing", "buffering"]


class MusicAssistantPlayer:
    def __init__(self, player_name: str, ha_url: str = HOME_ASSISTANT_URL, token: str = HOME_ASSISTANT_TOKEN):
        self.name = player_name
        self.ha_url = ha_url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._original_state = PlayerState({})

    def get_original_state(self) -> PlayerState:
        return self._original_state

    def set_original_state(self, state):
        self._original_state = state

    def _call_service(self, domain: str, service: str, data: dict):
        url = f"{self.ha_url}/api/services/{domain}/{service}"
        response = self.session.post(url, json=data, timeout=40)
        response.raise_for_status()
        return response

    def get_state(self) -> PlayerState:
        url = f"{self.ha_url}/api/states/{self.name}"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return PlayerState(response.json())

    def set_volume(self, level: float):
        safe_level = max(0.0, min(1.0, level))
        logger.debug(f"Setting volume of {self.name} to {safe_level}")
        self._call_service("media_player", "volume_set", {
            "entity_id": self.name,
            "volume_level": safe_level,
        })

    def pause(self):
        logger.info(f"Pausing media player {self.name}")
        self._call_service("media_player", "media_pause", {
            "entity_id": self.name,
        })

    def play(self):
        logger.info(f"Playing media player {self.name}")
        self._call_service("media_player", "media_play", {
            "entity_id": self.name,
        })

    def fetch_state(self):
        self._original_state = self.get_state()
        logger.debug(f"Storing original state for {self.name}: {self._original_state}")

    # Calls the API
    def get_volume(self) -> float:
        state = self.get_state()
        vol = state.get_volume()
        logger.debug(f"Current volume for {self.name} is {vol}")
        return vol

# This calculates the steps, but does not do the waiting, so that multiple players can be
# faded out together without needing to use threads. The caller can call step() repeatedly
# with a sleep in between, until it returns True to indicate it's done.
# Could have used threads to do this, but trying to minimise resource usage on the Pi.
# Also, this needs to be called by an HTTP endpoint, so I don't like to add extra
# treads in an HTTP server.
class PlayerFadeOut:
    """Gradually fade out volume over multiple steps."""

    def __init__(self, ma_player: MusicAssistantPlayer, target_volume: float = 0.0, num_steps: int = 10):
        self.ma_player = ma_player
        self.initial_volume = ma_player.get_volume()
        self.volumes = PlayerFadeOut.calculate_volume_steps(num_steps, self.initial_volume, target_volume)
        self.current_step = 0

    @staticmethod
    def calculate_volume_steps(num_steps, current_volume, target_volume) -> List[float]:
        if target_volume > 1.0:
            logger.warning(f"Cannot raise volume over 1.0, changing target_volume from {target_volume} to 1.0")
            target_volume = 1.0
        if current_volume is None or num_steps <= 0:
            return [target_volume]

        step = (current_volume - target_volume) / num_steps
        volumes = [current_volume - i * step for i in range(num_steps)]
        if not volumes or volumes[-1] != target_volume:
            volumes.append(target_volume)
        return volumes

    def step(self) -> bool:
        """Execute one step of the fade out. Returns True when complete."""
        if self.initial_volume is None:
            logger.info(f"Could not get initial volume for Music Assistant player, skipping fade out")
            return True
        if self.initial_volume == 0:
            logger.info(f"Initial volume is already 0 for Music Assistant player, skipping fade out")
            return True
        if self.current_step == 0:
            logger.info(f"Starting fade out of {self.ma_player.name} from {self.volumes[0]} to {self.volumes[-1]}")
        if self.current_step < len(self.volumes):
            new_volume = self.volumes[self.current_step]
            self.ma_player.set_volume(new_volume)
            self.current_step += 1
            return False
        else:
            self.ma_player.pause()
            logger.info("Paused Music Assistant playback")
            return True


class PlayerFadeUp:
    """Gradually fade up volume over multiple steps."""

    def __init__(self, ma_player: MusicAssistantPlayer, target_volume: float = 1.0, num_steps: int = 10):
        self.ma_player = ma_player
        self.last_known_volume = ma_player.get_volume() or 0
        self.volumes = PlayerFadeUp.calculate_volume_steps(num_steps, self.last_known_volume, target_volume)
        self.current_step = 0

    @staticmethod
    def calculate_volume_steps(num_steps, current_volume, target_volume) -> List[float]:
        if num_steps <= 0 or current_volume is None:
            return [target_volume]

        volume_step = (target_volume - current_volume) / num_steps
        volumes = [current_volume + i * volume_step for i in range(num_steps)]
        if not volumes or volumes[-1] != target_volume:
            volumes.append(target_volume)
        return volumes

    # Returns True when completed, either because the target volume has been reached
    # or because someone has altered the volume via another input.
    def step(self) -> bool:
        """Execute one step of the fade up. Returns True when complete."""
        if self.current_step == 0:
            logger.info(f"Starting fade up of {self.ma_player.name} from {self.volumes[0]} to {self.volumes[-1]}")
        if self.current_step < len(self.volumes):
            # if the current volume has changed since the last step, return True to indicate we're done,
            # as something else has changed the volume
            current_volume = self.ma_player.get_volume()
            if current_volume is not None and not self.similar_enough(current_volume, self.last_known_volume):
                logger.info(f"Volume for {self.ma_player.name} changed externally during fade up (from {self.last_known_volume} to {current_volume}), stopping fade up")
                return True # done
            new_volume = self.volumes[self.current_step]
            self.ma_player.set_volume(new_volume)
            self.last_known_volume = new_volume
            self.current_step += 1
            if self.current_step < len(self.volumes):
                return False  # not done yet
            else:
                logger.info(f"Finished fade up of {self.ma_player.name}")
            return True
        else:
            return True  # done

    # Sometimes the volume that set comes back as a slightly different volume to do numbers and rounding
    # and maths.
    def similar_enough(self, vol1: float, vol2: float, threshold: float = 0.1) -> bool:
        return abs(vol1 - vol2) <= threshold


def fade_out(ma_players: List[MusicAssistantPlayer], duration: float, steps: int = 10):
    """Gradually fade out the volume of the given Music Assistant players over the specified duration and steps, then stop them.

    Args:
        mpd_processes: List of MusicAssistantPlayer instances to fade out
        duration: Total duration in seconds for the fade out
        steps: Number of volume steps for the fade out
    """
    fade_outs = []
    for player in ma_players:
        if player.get_original_state().playing():
            fade_outs.append(PlayerFadeOut(player, target_volume=0, num_steps=steps))

    if not fade_outs:
        logger.info("No Music Assistant players to pause")

    step_time = duration / steps if steps > 0 else duration

    while fade_outs:
        for fade in fade_outs[:]:
            if fade.step():
                fade_outs.remove(fade)
        if fade_outs:
            time.sleep(step_time)


def fade_up(players_and_target_volumes: List[Tuple[MusicAssistantPlayer, float]], duration: float, steps: int = 10):
    """Gradually fade up the volume of the given Music Assistant players over the specified duration and steps.

    Args:
        mpd_processes_and_target_volumes: List of tuples of (MusicAssistantPlayer, target_volume)
        duration: Total duration in seconds for the fade up
        steps: Number of volume steps for the fade up
    """
    fade_ups = []
    for player, target_volume in players_and_target_volumes:
        fade_ups.append(PlayerFadeUp(player, target_volume=target_volume, num_steps=steps))

    step_time = duration / steps if steps > 0 else duration

    while fade_ups:
        for fade in fade_ups[:]:
            if fade.step():
                fade_ups.remove(fade)
        if fade_ups:
            time.sleep(step_time)

class MusicAssistant:
    def __init__(self, players: list[MusicAssistantPlayer], ha_url: str = HOME_ASSISTANT_URL, token: str = HOME_ASSISTANT_TOKEN):
        self.players = players

    def fetch_current_state(self):
        for player in self.players:
            player.fetch_state()

    def fade_out_and_pause(self):
        fade_out(self.players, duration=4, steps=10)

    def restore_original_state(self):
        playing_players = [player for player in self.players if player.get_original_state().playing()]
        if playing_players:
            for player in playing_players:
                player.play()

            # give the buffers time to get their glitches out
            time.sleep(1)

            fade_up([(player, player.get_original_state().get_volume()) for player in playing_players], duration=5, steps=10)

    @staticmethod
    def build_for_players_with_names(names):
        players = [MusicAssistantPlayer(f"media_player.{name}") for name in names]
        return MusicAssistant(players)

class MusicAssistantState:

    @staticmethod
    def save(music_assistant, file_path = MUSIC_ASSISTANT_STATE_FILE):
        music_assistant_state = {}
        music_assistant_state["playing_players"] = [ { "name": player.name, "original_state": player.get_original_state().state } for player in music_assistant.players ]

        data_json = json.dumps(music_assistant_state, sort_keys=True)
        with open(file_path, "w") as f:
            f.write(data_json)

    @staticmethod
    def load(file_path=MUSIC_ASSISTANT_STATE_FILE) -> MusicAssistant:
        with open(file_path, "r") as f:
            music_assistant_state = json.load(f)
        playing_players = music_assistant_state["playing_players"]
        if playing_players and isinstance(playing_players, list):
            players = []
            for player_dict in playing_players:
                player = MusicAssistantPlayer(player_dict["name"])
                player.set_original_state(PlayerState(player_dict["original_state"]))
                players.append(player)
            return MusicAssistant(players=players)
        else:
            logger.warning("Could not load playing players from saved state. Returning MusicAssistant with no players")
            logger.warning(music_assistant_state)
            return MusicAssistant([])

    """
        Do not restore any state that is more than 5 minutes old
    """
    @staticmethod
    def fresh(max_age_mins = 5, file_path = MUSIC_ASSISTANT_STATE_FILE) -> bool:
        max_age_seconds = max_age_mins * 60
        try:
            mtime = os.path.getmtime(file_path)
        except FileNotFoundError:
            return False
        return (time.time() - mtime) < max_age_seconds

    @staticmethod
    def clear(file_path = MUSIC_ASSISTANT_STATE_FILE):
        Path(file_path).unlink(missing_ok=True)
