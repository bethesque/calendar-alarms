import asyncio
import time
import requests
from bleak import BleakScanner

# ================= CONFIG =================

ENDPOINTS = {
    "single": "http://localhost:5000/button/single",
    "double": "http://localhost:5000/button/double",
    "long":   "http://localhost:5000/button/long",
}

DOUBLE_WINDOW = 0.7
LONG_THRESHOLD = 1.5
COOLDOWN = 0.75

# ================= STATE =================

press_events = []
last_packet_time = 0
burst_start = 0
in_burst = False
last_trigger = 0


# ================= HTTP =================

def trigger(event):
    global last_trigger

    now = time.time()

    if now - last_trigger < COOLDOWN:
        return

    last_trigger = now

    print(f"[TRIGGER] {event}")

    try:
        print(event)
        #requests.get(ENDPOINTS[event], timeout=2)
    except Exception as e:
        print(f"[HTTP ERROR] {e}")


# ================= BLE CALLBACK =================

def callback(device, advertisement_data):
    global last_packet_time, burst_start, in_burst

    if not device.name or not device.name.startswith("SBBT"):
        return

    if 2985 not in advertisement_data.manufacturer_data:
        return

    now = time.time()

    # start of new burst
    if not in_burst:
        in_burst = True
        burst_start = now
        press_events.append(now)

    last_packet_time = now


# ================= CLASSIFIER =================

async def classifier():
    global in_burst, press_events

    while True:
        await asyncio.sleep(0.05)

        if not in_burst:
            continue

        now = time.time()

        # wait until advertisement burst stops
        if now - last_packet_time < 0.25:
            continue

        in_burst = False

        burst_duration = last_packet_time - burst_start

        # long press
        if burst_duration >= LONG_THRESHOLD:
            trigger("long")
            press_events = []
            continue

        # wait briefly for possible second press
        await asyncio.sleep(DOUBLE_WINDOW)

        recent = [
            t for t in press_events
            if time.time() - t < DOUBLE_WINDOW + 0.5
        ]

        if len(recent) >= 2:
            trigger("double")
        else:
            trigger("single")

        press_events = []


# ================= MAIN =================

async def main():
    print("Starting BLE scanner...")

    scanner = BleakScanner(callback)
    await scanner.start()

    asyncio.create_task(classifier())

    while True:
        await asyncio.sleep(1)

asyncio.run(main())