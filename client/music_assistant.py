import json
from urllib import request, error

"""
Calls a webhook on Home Assistant to toggle between pause and play for the given player.
"""
def toggle_pause_play(home_assistant_url, player):
    url = f"{home_assistant_url}/api/webhook/media_player_toggle_pause_play"

    data = json.dumps({
        "player": player,
    }).encode("utf-8")

    req = request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=5) as response:
            response_body = response.read().decode("utf-8")

    except error.HTTPError as e:
        # Equivalent to response.raise_for_status()
        raise RuntimeError(
            f"HTTP {e.code}: {e.read().decode('utf-8')}"
        ) from e


"""
Calls a webhook on Home Assistant to ungroup and pause playback for the given player.
"""
def pause_player(home_assistant_url, player):
    url = f"{home_assistant_url}/api/webhook/media_player_pause"

    data = json.dumps({
        "player": player,
    }).encode("utf-8")

    req = request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=5) as response:
            response_body = response.read().decode("utf-8")

    except error.HTTPError as e:
        # Equivalent to response.raise_for_status()
        raise RuntimeError(
            f"HTTP {e.code}: {e.read().decode('utf-8')}"
        ) from e
