from evdev import InputDevice, ecodes, list_devices
import argparse
import yaml
import logging
from index import Config, toggle
import time
import subprocess

logger = logging.getLogger(__name__)


BT006_ADDRESS = "41:42:E2:24:3A:CE"
BT006_NAME = "BT006 Keyboard"

def find_bt006():
    """Return the BT006 input device, or None if it isn't connected."""
    for path in list_devices():
        device = InputDevice(path)

        if device.name == BT006_NAME:
            return device

        device.close()

    return None


def connect_bt006():
    """Ask BlueZ to connect to the BT006."""
    print(f"Attempting to connect to BT006 ({BT006_ADDRESS})...")

    result = subprocess.run(
        ["bluetoothctl", "connect", BT006_ADDRESS],
        capture_output=True,
        text=True,
        timeout=15,
    )

    if result.returncode == 0:
        print("Bluetooth connection successful")
        return True

    print(f"Bluetooth connection failed: {result.stdout.strip()}")
    return False


def listen_for_bt006(stop_alarm):
    while True:
        device = find_bt006()

        if device is None:
            print("BT006 input device not found")

            connect_bt006()

            # Give BlueZ time to establish the HID connection
            # and create the /dev/input/eventX device.
            for _ in range(10):
                time.sleep(1)

                device = find_bt006()
                if device is not None:
                    break

        if device is None:
            print("BT006 still not connected; retrying...")
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
            # The Bluetooth device disappeared while reading events.
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