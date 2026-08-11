import subprocess
import time
import os

"""
Not currently used. Shell script is used instead.
"""

DEVICE_MAC = os.environ['BLUETOOTH_SPEAKER_MAC']

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def bluetooth_connect(mac):
    print("Connecting to Bluetooth device...")

    process = subprocess.run(
        ["bluetoothctl"],
        input=f"connect {mac}\nquit\n",
        text=True,
        capture_output=True
    )

    print(process.stdout)
    return "Connection successful" in process.stdout

def get_bt_sink():
    result = run("pactl list short sinks")
    for line in result.stdout.splitlines():
        if "bluez" in line:
            return line.split()[1]
    return None

def wait_for_sink(timeout=15):
    print("Waiting for Bluetooth audio sink...")
    for _ in range(timeout):
        sink = get_bt_sink()
        if sink:
            print(f"Found sink: {sink}")
            return sink
        time.sleep(1)
    return None

def set_default_sink(sink):
    print(f"Setting default sink: {sink}")
    run(f"pactl set-default-sink {sink}")

def setup_bluetooth_audio():
    # Try connecting
    for attempt in range(3):
        if bluetooth_connect(DEVICE_MAC):
            break
        print("Retrying connection...")
        time.sleep(2)

    # Wait for audio sink
    sink = wait_for_sink()
    if not sink:
        print("ERROR: No Bluetooth sink found")
        return False

    set_default_sink(sink)
    print("Bluetooth audio ready ✅")
    return True


if __name__ == "__main__":
    setup_bluetooth_audio()