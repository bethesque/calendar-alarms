from evdev import InputDevice, ecodes, list_devices
import argparse
import yaml
import logging
from index import Config, toggle

logger = logging.getLogger(__name__)

def find_bt006():
    """Find the BT006 Bluetooth media controller."""
    for path in list_devices():
        device = InputDevice(path)
        if device.name == "BT006 Keyboard":
            return device

    return None


def handle_bt006_button(event):
    """Handle a button event from the BT006.

    Returns True when the Play/Pause button is pressed.
    """
    if event.type != ecodes.EV_KEY:
        return False

    # value == 1 means key down.
    # Ignore value == 0 (key up) and value == 2 (key repeat).
    if event.value != 1:
        return False

    if event.code == ecodes.KEY_PLAYPAUSE:
        return True

    return False


def listen_for_bt006(audio_config: dict):
    device = find_bt006()

    if device is None:
        raise RuntimeError("BT006 Keyboard not found")

    print(f"Listening for buttons on {device.path}: {device.name}")

    for event in device.read_loop():
        if handle_bt006_button(event):
            print("BT006 Play/Pause pressed")
            toggle(audio_config)
            # Call your calendar alarm stop function here.
            # stop_calendar_alarm()


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

    listen_for_bt006(config.app_config)