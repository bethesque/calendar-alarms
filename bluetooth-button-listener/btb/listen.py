import asyncio
import time
import logging
import requests
import argparse
import os
import json
from functools import partial
import http.client
from bleak import BleakScanner

# Configure app logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)

# Configure Bleak logging
bleak_logger = logging.getLogger("bleak")
bleak_logger.setLevel(getattr(logging, os.getenv("BLEAK_LOG_LEVEL", "INFO").upper(), logging.INFO))

# Configure HTTP logging
http.client.HTTPConnection.debuglevel = int(os.getenv("HTTP_LOG_LEVEL", "0") or 0)  # 0: disabled, 1: enabled

# Think this is the same for all Shelly Blu 1 buttons
DEFAULT_SERVICE_UUID = "0000fcd2-0000-1000-8000-00805f9b34fb"

LOCKOUT = 2  # Number of seconds, ignore rest of a click-event burst
last_trigger_time = 0

# Telemetry-only broadcasts (no button object) arrive in bursts of ~30
# near-identical packets every few hours. Battery level barely moves
# between bursts, so we rate-limit how often we actually log it.
TELEMETRY_LOG_LOCKOUT = 60  # seconds
last_telemetry_log_time = 0

SHELLY_BLU1_OBJECT_ID = 0x3A  # BTHome object ID for Shelly BLU1 button event

# BTHome v2 object id -> value byte-length, per bthome.io/format and Shelly's
# own BLU decoder scripts. Extend this if new object ids show up in logs.
BTHOME_OBJECT_LENGTHS = {
    0x00: 1,  # packet id (pid)
    0x01: 1,  # battery %
    0x02: 2,  # temperature (int16)
    0x03: 2,  # humidity (uint16)
    0x05: 3,  # illuminance (uint24)
    0x21: 1,  # motion
    0x2d: 1,  # window
    0x2e: 1,  # humidity (uint8 variant)
    SHELLY_BLU1_OBJECT_ID: 1,  # button event
}


def parse_bthome(payload):
    """
    Walk a BTHome v2 service-data payload as a TLV sequence, yielding
    (object_id, value_bytes) pairs.

    Shelly BLU buttons include extra objects (pid, battery, etc.) in every
    advertisement, and continue beaconing with a "no click" button value
    between presses. Rather than assume the button object is at a fixed
    offset, we walk the whole sequence and pick it out by id.

    If we hit an object id with an unknown length, we can no longer know
    where the next field starts, so we stop walking. This is logged at
    debug (not warning) level since these are routine/expected diagnostic
    fields we simply haven't catalogued, not error conditions.
    """
    i = 1  # byte 0 is the BTHome device-info byte, not an object
    while i < len(payload):
        obj_id = payload[i]
        length = BTHOME_OBJECT_LENGTHS.get(obj_id)
        if length is None:
            logging.debug(
                f"Unrecognised object id {obj_id:#x} at offset {i}, "
                f"stopping parse of payload: {payload.hex()}"
            )
            return
        value = payload[i + 1: i + 1 + length]
        if len(value) < length:
            logging.debug(
                f"Truncated value for object id {obj_id:#x}, "
                f"payload: {payload.hex()}"
            )
            return
        yield obj_id, value
        i += 1 + length


def extract_button_event(payload):
    """
    Pure helper: given a raw BTHome payload (bytes), return a dict with
    whatever fields we could find:
        {"battery": int|None, "event": int|None}

    "event" is None if no button object was present (e.g. a pure
    telemetry/idle beacon), 0 if present but reporting "no click" (idle
    beacon between presses), or 1/2/3/4/... for an actual click type.

    Split out from the bleak callback so it can be unit tested directly
    against raw payload bytes without needing to fake bleak's
    device/advertisement_data objects.
    """
    battery = None
    event = None
    for obj_id, value in parse_bthome(payload):
        if obj_id == 0x01:
            battery = value[0]
        elif obj_id == SHELLY_BLU1_OBJECT_ID:
            event = value[0]
    return {"battery": battery, "event": event}


def trigger(event, endpoints):
    url = endpoints.get(event)
    if not url:
        logging.info(f"No URL configured for event {event}, ignoring")
        return

    logging.info(f"Received event {event}, calling endpoint {url}")

    try:
        response = requests.post(url, timeout=3, verify=False)
        logging.info(f"Response code: {response.status_code}")
    except Exception:
        logging.exception(f"Exception invoking endpoint {url}")


def _capture_payload(path, device, advertisement_data, payload):
    """Append a raw sighting to a JSONL file for later replay/testing."""
    try:
        with open(path, "a") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "mac": device.address,
                "name": device.name,
                "rssi": advertisement_data.rssi,
                "payload_hex": payload.hex(),
            }) + "\n")
    except Exception:
        logging.exception(f"Failed to write payload capture to {path}")


def callback(button_mac, service_uuid, endpoints, capture_path, device, advertisement_data):
    global last_trigger_time, last_telemetry_log_time

    # 1. MAC address check — cheapest, filters out all other devices
    if device.address != button_mac:
        return

    # 2. Name sanity check
    if not device.name or not device.name.startswith("SBBT"):
        logging.warning(f"MAC matched but unexpected device name: {device.name}")
        return

    # 3. Service UUID check
    sd = advertisement_data.service_data
    if service_uuid not in sd:
        return

    payload = sd[service_uuid]

    if capture_path:
        _capture_payload(capture_path, device, advertisement_data, payload)

    # 4. Validate payload length
    if len(payload) < 2:
        logging.warning(f"Payload too short: {payload.hex()}")
        return

    # 5. Pull out battery/event fields by walking the TLV structure.
    #    Note: we now always parse before checking any lockout, because
    #    telemetry-only broadcasts (no button object) need their battery
    #    level logged regardless of the click lockout state below — the
    #    two lockouts are independent and gate different kinds of packets.
    parsed = extract_button_event(payload)
    event = parsed["event"]
    battery = parsed["battery"]

    if event is None:
        # No button-event object present — this is a telemetry-only
        # broadcast, not a click. Log the battery level, rate-limited
        # since these arrive in bursts of ~30 near-identical packets
        # every few hours and battery barely moves between bursts.
        now = time.time()
        if battery is not None and now - last_telemetry_log_time >= TELEMETRY_LOG_LOCKOUT:
            last_telemetry_log_time = now
            logging.info(
                f"Telemetry from {device.address} ({device.name}) | "
                f"RSSI: {advertisement_data.rssi} | Battery: {battery}%"
            )
        return

    # 6. Click lockout — a button object is present (either a real click
    #    or an idle "no click" beacon). Bail early on repeats within the
    #    window before doing anything further.
    now = time.time()
    if now - last_trigger_time < LOCKOUT:
        return

    # 8. Validate event value is one we recognise
    if event not in endpoints:
        logging.warning(f"Unknown event value: {event}, ignoring")
        return

    last_trigger_time = now

    logging.info(
        f"Packet from {device.address} ({device.name}) | "
        f"RSSI: {advertisement_data.rssi} | "
        f"Payload: {payload.hex()} | "
        f"Battery: {battery} | "
        f"Event: {event}"
    )
    trigger(event, endpoints)


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--button-mac-address",
        help="The Service UUID of the bluetooth button to listen to.",
    )

    parser.add_argument(
        "--service-uuid",
        help="The Service UUID of the bluetooth button to listen to.",
    )

    parser.add_argument(
        "--single-click-endpoint",
        help="The endpoint to send an HTTP request to on receiving a single click",
    )

    parser.add_argument(
        "--double-click-endpoint",
        help="The endpoint to send an HTTP request to on receiving a double click",
    )

    parser.add_argument(
        "--long-click-endpoint",
        help="The endpoint to send an HTTP request to on receiving a long click",
    )

    parser.add_argument(
        "--capture-payloads",
        help="Optional path to a JSONL file. Every matching advertisement's "
             "raw payload is appended here (mac, name, rssi, payload_hex, "
             "timestamp) so it can be fed into the test suite later.",
    )

    args = parser.parse_args()

    service_uuid = args.service_uuid or os.getenv("SERVICE_UUID", DEFAULT_SERVICE_UUID)
    button_mac_address = args.button_mac_address or os.getenv("BUTTON_MAC_ADDRESS")
    capture_path = args.capture_payloads or os.getenv("CAPTURE_PAYLOADS")
    endpoints = {
        1: args.single_click_endpoint or os.getenv("SINGLE_CLICK_ENDPOINT"),
        2: args.double_click_endpoint or os.getenv("DOUBLE_CLICK_ENDPOINT"),
        4: args.long_click_endpoint or os.getenv("LONG_CLICK_ENDPOINT")
    }

    return (service_uuid, button_mac_address, endpoints, capture_path)


def validate_arguments(button_mac_address, endpoints):
    if button_mac_address is None:
        print("Must provide --button-mac-address or env BUTTON_MAC_ADDRESS")
        exit(1)

    if all(value is None for value in endpoints.values()):
        print("A --single-click-endpoint or env SINGLE_CLICK_ENDPOINT, --double-click--endpoint or DOUBLE_CLICK_ENDPOINT, or --long-click-endpoint or LONG_CLICK_ENDPOINT is required")
        exit(1)


async def main():
    service_uuid, button_mac_address, endpoints, capture_path = parse_arguments()
    validate_arguments(button_mac_address, endpoints)

    callback_partial = partial(callback, button_mac_address, service_uuid, endpoints, capture_path)
    logging.info(f"Listening for button {button_mac_address} with service {service_uuid}, endpoints: {endpoints}")
    if capture_path:
        logging.info(f"Capturing raw payloads to {capture_path}")

    scanner = BleakScanner(callback_partial)
    await scanner.start()

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())