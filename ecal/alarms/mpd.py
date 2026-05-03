import time
import logging
import musicpd
from typing import Optional, List, Tuple
import os
from contextlib import contextmanager
from ecal.env import MPD_HOST, MPD_PORT

logger = logging.getLogger(__name__)

"""
This module provides an interface to control the MPD daemon for playing audio files,
including functionality to fade in and fade out the volume.
It uses the python-musicpd library to communicate with the MPD daemon.
"""

@contextmanager
def mpd_connection():
    client = MpdClient(MPD_HOST, MPD_PORT)
    try:
        client.connect()
        yield client
    except Exception as e:
        logger.error(f"Error while connected to MPD: {e}")
        raise e
    finally:
        client.disconnect()

def wrapext(func):
    """Decorator to wrap errors in musicpd.MPDError"""
    errors=(OSError, TimeoutError)
    into = musicpd.MPDError
    def w_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except errors as err:
            strerr = str(err)
            if hasattr(err, 'strerror'):
                if err.strerror:
                    strerr = err.strerror
            raise into(strerr) from err
    return w_func


# https://kaliko.gitlab.io/python-musicpd/examples.html#dealing-with-exceptions
class LoggingClient(musicpd.MPDClient):
    """Plain client inheriting from MPDClient"""

    def __init__(self):
        # Set logging to debug level
        logging.basicConfig(level=logging.DEBUG,
                format='%(levelname)-8s %(module)-10s %(message)s')
        self.log = logging.getLogger(__name__)
        super().__init__()

    @wrapext
    def __getattr__(self, cmd):
        """Wrapper around MPDClient calls for abstract overriding"""
        self.log.debug('cmd: %s', cmd)
        return super().__getattr__(cmd)

class MpdClient:
    """Interface to control MPD daemon for playing audio files."""

    def __init__(self, host: str = 'localhost', port: int = 6600):
        """Initialize MPD client connection parameters.

        Args:
            host: MPD server hostname (default: localhost)
            port: MPD server port (default: 6600)
        """
        self.host = host
        self.port = port
        self.client: Optional[musicpd.MPDClient] = None

    def connect(self):
        """Establish connection to MPD daemon."""
        try:
            if self.client is None:
                self.client = LoggingClient()
                self.client.socket_timeout = 5.0
                self.client.connect(self.host, self.port)
            return self
        except (musicpd.ConnectionError, OSError) as e:
            logger.debug(f"Failed to connect to MPD at {self.host}:{self.port}: {e}")
            raise e

    def disconnect(self):
        """Disconnect from MPD daemon."""
        if self.client is not None:
            try:
                self.client.close()
                self.client.disconnect()
                logger.debug("Disconnected client from MPD")
            except (musicpd.ConnectionError, OSError) as e:
                logger.debug(f"Failed to disconnect from MPD: {e}")
            finally:
                self.client = None
        else:
            logger.debug("MPD client was not connected, nothing to disconnect")

    def is_running(self) -> bool:
        """Return True if MPD daemon is running and connectable."""
        try:
            if self.client is None:
                if not self.connect():
                    return False
            # Try to ping the server
            self.client.ping()
            return True
        except (musicpd.ConnectionError, OSError):
            self.client = None
            return False

    def _ensure_connected(self) -> bool:
        """Ensure we have an active connection to MPD."""
        if not self.is_running():
            return self.connect()
        return True

    def play_file(self, file_path: str):
        full_path = f"file://{os.path.abspath(file_path)}"

        try:
            self.client.clear()
            self.client.add(full_path)
            self.client.play()
            logger.debug(f"Playing file: {full_path}")
        except musicpd.CommandError as e:
            logger.error(f"Failed to play file {full_path}: {e}")
            raise e



    def set_volume(self, vol: int):
        try:
            # Clamp volume to 0-100 range
            vol = max(0, min(100, vol))
            self.client.setvol(vol)
            logger.debug(f"Set volume to {vol}")
        except musicpd.CommandError as e:
            logger.error(f"Failed to set volume: {e}")

    def stop(self):
        try:
            self.client.stop()
            self.client.clear()
            self.client.repeat(0)  # Disable repeat mode
            logger.debug("Stopped MPD playback")
        except musicpd.CommandError as e:
            logger.error(f"Failed to stop MPD: {e}")

    def get_volume(self) -> Optional[int]:
        try:
            status = self.client.status()
            volume = status.get('volume', '0')
            return int(volume)
        except (musicpd.CommandError, ValueError) as e:
            logger.debug(f"Failed to get volume: {e}")
            return None

# This calculates the steps, but does not do the waiting, so that multiple players can be
# faded out together without needing to use threads. The caller can call step() repeatedly
# with a sleep in between, until it returns True to indicate it's done.
# Could have used threads to do this, but trying to minimise resource usage on the Pi.
# Also, this needs to be called by an HTTP endpoint, so I don't like to add extra
# treads in an HTTP server.
class FadeOut:
    """Gradually fade out volume over multiple steps."""

    def __init__(self, mpd_process: MpdClient, target_volume: int = 0, num_steps: int = 10):
        self.mpd_process = mpd_process
        self.initial_volume = mpd_process.get_volume()
        # Convert to an array of volume levels to step through, from initial_volume down to target_volume
        self.percentages = FadeOut.calculate_volume_steps(num_steps, self.initial_volume, target_volume)
        self.current_step = 0

    """
    Returns percentages not vol steps, need to update
    """
    @staticmethod
    def calculate_volume_steps(num_steps, current_volume, target_volume) -> List[int]:
        if num_steps < 1:
            raise Exception(f"num_steps ({num_steps}) must be more than 0")
        volume_step = max(1, (current_volume - target_volume) // num_steps)
        volumes = list(reversed(range(target_volume, current_volume, volume_step)))
        if not volumes or volumes[-1] != target_volume:
            volumes.append(target_volume)
        return volumes

        #return list(reversed(range(0, 101, 100 // num_steps)))

    def step(self) -> bool:
        """Execute one step of the fade out. Returns True when complete."""
        if self.initial_volume is None:
            logger.info(f"Could not get initial volume for MPD player, skipping fade out")
            return True  # can't get volume, so just skip the fade out
        if self.initial_volume == 0:
            logger.info(f"Initial volume is already 0 for MPD player, skipping fade out")
            return True  # already at 0 volume, so we're done
        if self.current_step < len(self.percentages):
            percent = self.percentages[self.current_step]
            new_volume = max(0, self.initial_volume * percent // 100)
            self.mpd_process.set_volume(new_volume)
            self.current_step += 1
            return False  # not done yet
        else:
            self.mpd_process.stop()
            logger.info("Stopped MPD playback")
            return True  # done


class FadeUp:
    """Gradually fade up volume over multiple steps."""

    def __init__(self, mpd_process: MpdClient, target_volume: int = 100, num_steps: int = 10):
        self.mpd_process = mpd_process
        self.last_known_volume = mpd_process.get_volume() or 0
        # An array of volume levels to step through, from initial_volume up to target_volume
        self.volumes = FadeUp.calculate_volume_steps(num_steps, self.last_known_volume, target_volume)
        self.current_step = 0

    @staticmethod
    def calculate_volume_steps(num_steps, current_volume, target_volume) -> List[int]:
        volume_step = max(1, (target_volume - current_volume) // num_steps)
        volumes = list(range(current_volume, target_volume, volume_step))
        if not volumes or volumes[-1] != target_volume:
            volumes.append(target_volume)
        return volumes

    def step(self) -> bool:
        """Execute one step of the fade up. Returns True when complete."""
        if self.current_step < len(self.volumes):
            # if the current volume has changed since the last step, return True to indicate we're done,
            # as something else has changed the volume
            current_volume = self.mpd_process.get_volume()
            if current_volume is not None and not self.similar_enough(current_volume, self.last_known_volume):
                logger.info(f"Volume changed externally during fade up (from {self.last_known_volume} to {current_volume}), stopping fade up")
                return True  # done
            new_volume = self.volumes[self.current_step]
            self.mpd_process.set_volume(new_volume)
            self.last_known_volume = new_volume
            self.current_step += 1
            if self.current_step < len(self.volumes):
                return False  # not done yet
            else:
                logger.info("Finished fading up MPD playback")
            return True
        else:
            return True  # done


    # Sometimes the volume that set comes back as a slightly different volume to do numbers and rounding
    # and maths.
    def similar_enough(self, vol1: int, vol2: int, threshold: int = 2) -> bool:
        return abs(vol1 - vol2) <= threshold


def fade_out(mpd_processes: List[MpdClient], duration: float, steps: int = 10):
    """Gradually fade out the volume of the given MPD processes over the specified duration and steps, then stop them.

    Args:
        mpd_processes: List of MpdProcess instances to fade out
        duration: Total duration in seconds for the fade out
        steps: Number of volume steps for the fade out
    """
    fade_outs = []
    for player in mpd_processes:
        if player.is_running():
            fade_outs.append(FadeOut(player, target_volume=0, num_steps=steps))

    step_time = duration / steps if steps > 0 else duration

    while fade_outs:
        for fade in fade_outs[:]:
            if fade.step():
                fade_outs.remove(fade)
        if fade_outs:
            time.sleep(step_time)


def fade_up(mpd_processes_and_target_volumes: List[Tuple[MpdClient, int]], duration: float, steps: int = 10):
    """Gradually fade up the volume of the given MPD processes over the specified duration and steps.

    Args:
        mpd_processes_and_target_volumes: List of tuples of (MpdProcess, target_volume)
        duration: Total duration in seconds for the fade up
        steps: Number of volume steps for the fade up
    """
    fade_ups = []
    for player, target_volume in mpd_processes_and_target_volumes:
        fade_ups.append(FadeUp(player, target_volume=target_volume, num_steps=steps))

    step_time = duration / steps if steps > 0 else duration

    while fade_ups:
        for fade in fade_ups[:]:
            if fade.step():
                fade_ups.remove(fade)
        if fade_ups:
            time.sleep(step_time)
