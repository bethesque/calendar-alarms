import asyncio
import logging
import functools
from contextlib import asynccontextmanager
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import PlayerState

log = logging.getLogger(__name__)

#logging.getLogger("music_assistant_client").setLevel(logging.DEBUG)

def log_duration(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        t0 = asyncio.get_event_loop().time()
        try:
            return await func(*args, **kwargs)
        finally:
            elapsed = asyncio.get_event_loop().time() - t0
            log.info("[%s] took %.3fs", func.__name__, elapsed)
    return wrapper

@asynccontextmanager
async def _interval_timer(delay: float):
    t0 = asyncio.get_event_loop().time()
    yield
    elapsed = asyncio.get_event_loop().time() - t0
    remaining = delay - elapsed
    if remaining > 0:
        await asyncio.sleep(remaining)

async def _fade_down_player(client,
        player_id: str,
        player_name: str,
        start_volume: int,
        target_volume: int,
        duration_seconds: float,
        intervals: int,
    ) -> None:
        if target_volume >= start_volume:
            log.info("[%s] already at or below target %d%%, skipping.", player_name, target_volume)
            return

        step = (target_volume - start_volume) / intervals
        delay = duration_seconds / intervals

        log.info(
            "[%s] fading %d%% → %d%% over %.1fs in %d steps (Δ%+.1f%% every %.2fs)",
            player_name, start_volume, target_volume, duration_seconds, intervals, step, delay,
        )

        for i in range(1, intervals + 1):
            this_delay = delay if i < intervals else 0  # no need to delay after last step

            async with _interval_timer(this_delay):
                new_volume = max(0, min(100, round(start_volume + step * i)))
                await client.send_command(
                    "players/cmd/volume_set",
                    player_id=player_id,
                    volume_level=new_volume,
                )
                log.debug("  [%s] step %d/%d → %d%%", player_name, i, intervals, new_volume)

        log.info("[%s] fade complete.", player_name)

async def _pause_player(client, player_id: str, player_name: str ) -> None:
    log.info("Pausing [%s]", player_name)
    await client.send_command("players/cmd/pause", player_id=player_id)

async def _play_player(client, player_id: str, player_name: str ) -> None:
    log.info("Playing [%s]", player_name)
    await client.send_command("players/cmd/play", player_id=player_id)

async def _fade_up_player(
        client,
        player_id: str,
        player_name: str,
        start_volume: int,
        target_volume: int,
        duration_seconds: float,
        intervals: int,
    ) -> None:
        if start_volume >= target_volume:
            log.info("[%s] already at or above target %d%%, skipping.", player_name, target_volume)
            return

        step = (target_volume - start_volume) / intervals
        delay = duration_seconds / intervals

        log.info(
            "[%s] fading up %d%% → %d%% over %.1fs in %d steps (Δ%+.1f%% every %.2fs)",
            player_name, start_volume, target_volume, duration_seconds, intervals, step, delay,
        )

        for i in range(1, intervals + 1):
            this_delay = delay if i < intervals else 0  # no need to delay after last step
            async with _interval_timer(this_delay):
                new_volume = max(0, min(100, round(start_volume + step * i)))
                await client.send_command(
                    "players/cmd/volume_set",
                    player_id=player_id,
                    volume_level=new_volume,
                )
                log.debug("  [%s] step %d/%d → %d%%", player_name, i, intervals, new_volume)

            # if i < intervals:
            #     await asyncio.sleep(delay)

            #     player = self.client.players.get(player_id)
            #     if player is None:
            #         log.warning("[%s] player disappeared, aborting fade.", player_name)
            #         return
            #     actual = player.volume_level
            #     if abs(actual - new_volume) > 3:
            #         log.warning(
            #             "[%s] volume mismatch — expected ~%d%%, got %d%%. Aborting fade.",
            #             player_name, new_volume, actual,
            #         )
            #         return

        log.info("[%s] fade up complete.", player_name)

class MusicAssistant:

    def __init__(self, url: str, token: str | None = None):
        self.url = url
        self.token = token
        self._client: MusicAssistantClient | None = None

    async def __aenter__(self) -> "MusicAssistant":
        self._client = MusicAssistantClient(self.url, None, token=self.token)
        try:
            await self._client.__aenter__()
            init = asyncio.Event()

            async def _listen() -> None:
                try:
                    await self._client.start_listening(init)
                except Exception as exc:
                    log.error("Music Assistant Listener error: %s", exc)
                    init.set()  # unblock init.wait() on failure

            asyncio.create_task(_listen())
            await init.wait()
            return self
        except Exception:
            await self._client.__aexit__(None, None, None)
            self._client = None
            raise

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.__aexit__(*args)
            self._client = None

    @property
    def client(self) -> MusicAssistantClient:
        if self._client is None:
            raise RuntimeError("Not connected — use 'async with MusicAssistant(...) as ma'")
        return self._client

    def playing(self) -> bool:
        return any(self.playing_players())

    def playing_players(self):
        return [
            p for p in self.client.players
            if p.playback_state == PlayerState.PLAYING
        ]

    def fetch_current_state(self) -> list[dict]:
        return [{ "player_id": p.player_id, "volume_level": p.volume_level } for p in self.playing_players()]

    async def dip_voume(self):
        await self.fade_down(target_volume=0, duration_seconds=3, intervals=20)

    @log_duration
    async def fade_down(
        self,
        target_volume: int,
        duration_seconds: float,
        intervals: int,
    ) -> None:
        players = self.playing_players()
        if not players:
            log.warning("No players are currently playing — nothing to fade.")
            return

        for p in players:
            log.info("  • %s  (id=%s, volume=%d%%)", p.name, p.player_id, p.volume_level)

        tasks = [
                    _fade_down_player(
                        client=self.client,
                        player_id=p.player_id,
                        player_name=p.name,
                        start_volume=p.volume_level,
                        target_volume=target_volume,
                        duration_seconds=duration_seconds,
                        intervals=intervals,
                    )
                    for p in players
                ]
        timeout = duration_seconds + 2  # small grace period
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            log.warning("Fade down timed out after %.1fs, continuing anyway.", timeout)

    @log_duration
    async def pause(self) -> None:
        players = self.playing_players()
        if not players:
            log.info("No players are currently playing — nothing to pause.")
            return

        tasks = [
                    _pause_player(
                        client=self.client,
                        player_id=p.player_id,
                        player_name=p.name,
                    )
                    for p in players
                ]
        timeout = 5
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            log.warning("Pause timed out after %.1fs, continuing anyway.", timeout)

    @log_duration
    async def play(self, player_ids: list[str]) -> None:
        players = [p for p in self.client.players if p.player_id in player_ids]
        if not players:
            log.info("No players to resume playing.")
            return

        tasks = [
                    _play_player(
                        client=self.client,
                        player_id=p.player_id,
                        player_name=p.name,
                    )
                    for p in players
                ]
        timeout = 5
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            log.warning("Pause timed out after %.1fs, continuing anyway.", timeout)

    @log_duration
    async def fade_up_restore(
        self,
        player_volumes: list[dict],
        duration_seconds: float,
        intervals: int,
    ) -> None:
        tasks = []
        for player_dict in player_volumes:
            player_id = player_dict["player_id"]
            target_volume = player_dict["volume_level"]
            player = self.client.players.get(player_id)
            if player is None:
                log.warning("[%s] player not found, skipping.", player_id)
                continue
            tasks.append(
                _fade_up_player(
                    client=self.client,
                    player_id=player.player_id,
                    player_name=player.name,
                    start_volume=player.volume_level,
                    target_volume=target_volume,
                    duration_seconds=duration_seconds,
                    intervals=intervals,
                )
            )
        timeout = duration_seconds + 15
        try:
            async with asyncio.timeout(timeout):
                await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            log.warning("Fade up timed out after %.1fs, continuing anyway.", timeout)

    @asynccontextmanager
    async def _interval_timer(self, delay: float):
        t0 = asyncio.get_event_loop().time()
        yield
        elapsed = asyncio.get_event_loop().time() - t0
        remaining = delay - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

    @asynccontextmanager
    async def log_time(label: str):
        t0 = asyncio.get_event_loop().time()
        yield
        elapsed = asyncio.get_event_loop().time() - t0
        log.debug("[%s] took %.3fs", label, elapsed)


async def announce(
    url: str,
    token: str | None,
    announcement_coro,
    target_volume: int,
    duration_seconds: float,
    intervals: int,
) -> None:
    async with MusicAssistant(url, token) as ma:
        state = await ma.fade_down(target_volume, duration_seconds, intervals)
        await announcement_coro
        await ma.fade_up_restore(state, duration_seconds, intervals)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from vcal.env import MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN

    async def main():
        async with MusicAssistant(MUSIC_ASSISTANT_URL, MUSIC_ASSISTANT_TOKEN) as ma:
            state = ma.fetch_current_state()
            print("Playing?", ma.playing_players())
            print("Current state:", state)
            await ma.fade_down(target_volume=5, duration_seconds=5, intervals=20)
            await asyncio.sleep(3)
            await ma.fade_up_restore(state, duration_seconds=5, intervals=20)


    asyncio.run(main())