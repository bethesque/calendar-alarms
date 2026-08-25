from evdev import InputDevice, ecodes, list_devices


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


def listen_for_bt006():
    device = find_bt006()

    if device is None:
        raise RuntimeError("BT006 Keyboard not found")

    print(f"Listening for buttons on {device.path}: {device.name}")

    for event in device.read_loop():
        if handle_bt006_button(event):
            print("BT006 Play/Pause pressed")
            # Call your calendar alarm stop function here.
            # stop_calendar_alarm()


if __name__ == "__main__":
    listen_for_bt006()