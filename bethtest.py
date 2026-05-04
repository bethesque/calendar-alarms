#!/usr/bin/env python3

import requests
import time
import logging
import sys

from typing import Optional, List, Tuple

from ecal.env import PLAYERS, LOG_LEVEL
from ecal.log_config import setup_logging_for_alarms

# Configure the root logger to output to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)



logger = logging.getLogger(__name__)


from ecal.music_assistant import MusicAssistant, MusicAssistantPlayer, MusicAssistantState

setup_logging_for_alarms(LOG_LEVEL, None)

def main():
    players = [MusicAssistantPlayer(f"media_player.{name}") for name in PLAYERS]
    ma = MusicAssistant(players)

    ma.fetch_current_state()
    ma_state = MusicAssistantState()
    ma_state.save(ma)

    ma.fade_out_and_pause()

    time.sleep(3)

    ma = ma_state.load()

    ma.restore_original_state()


if __name__ == "__main__":
    main()
