from evdev import InputDevice, ecodes, list_devices
import argparse
import yaml
import logging
from index import Config, toggle

logger = logging.getLogger(__name__)

import time

from evdev import InputDevice, ecodes, list_devices


BT006_NAME = "BT006 Keyboard"


def find_bt006():
    for path in list_devices():
        device = InputDevice(path)

        if device.name == BT006_NAME:
            return device

        device.close()

    return None


def listen_for_bt006(stop_alarm):
    while True:
        device = find_bt006()

        if device is None:
            print("BT006 not connected; waiting...")
            time.sleep(5)
            continue

        print(f"BT006 connected on {device.path}")

        try:
            for event in device.read_loop():
                if (
                    event.type == ecodes.EV_KEY
                    and event.value == 1
                    and event.code == ecodes.KEY_PLAYPAUSE
                ):
                    print("BT006 Play/Pause pressed")
                    stop_alarm()

        except OSError as e:
            # The Bluetooth device disappeared while we were reading it.
            print(f"BT006 disconnected: {e}")

        finally:
            device.close()

        print("BT006 disconnected; waiting for reconnect...")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Audio control service")

    parser.add_argument(
        "--conf",
        default="config.yaml",
    )

    args = parser.parse_args()

    with open(args.conf) as f:
        config = Config(**yaml.safe_load(f))

    uvicorn_args = config.uvicorn_kwargs

    parser = argparse.ArgumentParser(description="Audio control service")

    toggle_url = f"http://{config.host}:{config.port}/audio/toggle"
    stop_url = f"http://{config.host}:{config.port}/audio/stop"
    status_url = f"http://{config.host}:{config.port}/audio/status"
    logger.info(f"Starting audio client endpoints at {toggle_url}, {stop_url} and {status_url} with config {config.app_config}")

    def stop_calendar_alarm():
        toggle(config.app_config)

    listen_for_bt006(stop_calendar_alarm)