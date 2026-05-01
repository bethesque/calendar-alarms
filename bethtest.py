#!/usr/bin/env python3

import requests
import time
import logging
import sys
import http.client

HA_URL = "http://192.168.20.3:8123"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIwMGRkYWI1YzE5MWM0ODFkOGM1ZjBlMjIyYjZhYmY1YSIsImlhdCI6MTc3NzUyMDk4MywiZXhwIjoyMDkyODgwOTgzfQ.XXZC4F8QgUm8aSnwiWmAXX4GvDPq_5p_ifm-Lpz4tTY"
PLAYERS = ["media_player.kaypi"]

ALARM_MEDIA = "library://track/6620"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# Configure the root logger to output to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Optional: Enable low-level debugging to see raw HTTP headers/body
http.client.HTTPConnection.debuglevel = 1

# ------------------------
# Helpers
# ------------------------

def call_service(domain, service, data):
    url = f"{HA_URL}/api/services/{domain}/{service}"
    r = requests.post(url, headers=HEADERS, json=data, timeout=40)
    r.raise_for_status()

def get_state(player):
    url = f"{HA_URL}/api/states/{player}"
    r = requests.get(url, headers=HEADERS, timeout=40)
    r.raise_for_status()
    return r.json()

def set_volume(level, player):
    call_service("media_player", "volume_set", {
        "entity_id": player,
        "volume_level": level
    })

def pause(player):
    call_service("media_player", "media_pause", {
        "entity_id": player
    })

def play(player):
    call_service("media_player", "media_play", {
        "entity_id": player
    })

def play_alarm():
    call_service("media_player", "play_media", {
        "entity_id": player,
        "media_content_id": ALARM_MEDIA,
        "media_content_type": "music"
    })

# ------------------------
# Fade logic (via MA volume)
# ------------------------

def fade_volume(start, end, duration=3, steps=10, player):
    step_time = duration / steps
    delta = (end - start) / steps

    vol = start
    for _ in range(steps):
        vol += delta
        set_volume(max(0, min(1, vol)), player)
        time.sleep(step_time)

# ------------------------
# Main flow
# ------------------------

def main():
    player = PLAYERS[0]  # For simplicity, just use the first player
    # Get current state
    print("Checking current player state...")
    state = get_state(player)
    attrs = state.get("attributes", {})

    original_volume = attrs.get("volume_level", 0.5)
    was_playing = state.get("state") == "playing"

    print(f"Original volume: {original_volume}, was playing: {was_playing}")

    # 1. Fade down
    fade_volume(original_volume, 0, duration=4, player=player)

    # 2. Pause current playback
    if was_playing:
        pause(player)
        time.sleep(1)

    # 3. Set alarm volume higher
    # set_volume(0.8, player)

    print("PLAYING ALARM")
    time.sleep(5)

    # 4. Play alarm via Music Assistant
    #play_alarm()

    #fade_volume(0.2, 0.8, duration=5)

    # 5. Wait until alarm finishes
    # (poll state until it's no longer playing alarm)
    timeout = 300  # max 5 minutes
    start_time = time.time()

    # while True:
    #     time.sleep(2)

    #     state = get_state()
    #     current_state = state.get("state")

    #     # If stopped/idle → alarm finished
    #     if current_state in ["idle", "paused"]:
    #         break

    #     if time.time() - start_time > timeout:
    #         print("Alarm timeout reached")
    #         break



    # 7. Resume music if it was playing
    if was_playing:
        play(player)

    time.sleep(5)

    # 6. Restore previous volume
    fade_volume(0, original_volume, duration=10, player=player)

    print("Alarm cycle complete")

# ------------------------

if __name__ == "__main__":
    main()