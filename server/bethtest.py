import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

from music_assistant_client import MusicAssistantClient
from vcal.env import MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN


async def main():
    async with MusicAssistantClient(
        MUSIC_ASSISTANT_URL,
        None,
        token=MUSIC_ASSISTANT_TOKEN,
    ) as client:

        print("Connected")

        listener = asyncio.create_task(client.start_listening())

        # wait for players to arrive via websocket
        for _ in range(50):
            players = list(client.players)
            if players:
                break
            await asyncio.sleep(0.1)

        print(f"Found {len(players)} players")

        for p in players:
            print(p.player_id, p.name)

        listener.cancel()


if __name__ == "__main__":
    asyncio.run(main())