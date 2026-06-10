import requests
import logging

logger = logging.getLogger(__name__)

# Takes 0.06 of a second, rather than the 0.6 of a second it takes to determine this by using the websocket
def any_players_playing(music_assistant_url, token) -> bool:
    url = f"{music_assistant_url}/api"

    payload = {
        "command": "players/all"
    }

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        r = requests.post(url, json=payload, timeout=2, headers=headers)
        players = r.json()
        return any(player['playback_state'] == 'playing' for player in players)
    except Exception as e:
        logger.exception(f"Error checking if any Music Assistant players are playing at {music_assistant_url} ({type(e).__name__} - {e}) — assuming no players are playing")
        return False

def any_players_playing(music_assistant_url, token) -> bool:
    url = f"{music_assistant_url}/api"

    payload = {
        "command": "players/all"
    }

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        r = requests.post(url, json=payload, timeout=2, headers=headers)
        players = r.json()
        return any(player['playback_state'] == 'playing' for player in players)
    except Exception as e:
        logger.exception(f"Error checking if any Music Assistant players are playing at {music_assistant_url} ({type(e).__name__} - {e}) — assuming no players are playing")
        return False


