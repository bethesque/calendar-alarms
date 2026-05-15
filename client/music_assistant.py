import requests

def pause_player(home_assistant_url, access_token, player):
    response = requests.post(
        f"{home_assistant_url}/api/services/script/unjoin_and_pause",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "player": player,
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()
