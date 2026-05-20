import asyncio
import time
import logging
import requests
import argparse
import os
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
http.client.HTTPConnection.debuglevel = int(os.getenv("HTTP_LOG_LEVEL", "0") or 0) # 0: disabled, 1: enabled

# Think this is the same for all Shelly Blu 1 buttons
DEFAULT_SERVICE_UUID = "0000fcd2-0000-1000-8000-00805f9b34fb"

LOCKOUT = 2  # Number of seconds, ignore rest of burst
last_trigger_time = 0

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


def callback(button_mac, service_uuid, endpoints, device, advertisement_data):
    global last_trigger_time

    # filter device - Shelly Bluetooth Button Tough -> SBBT
    if not device.name or not device.name.startswith("SBBT"):
        return

    sd = advertisement_data.service_data
    if service_uuid not in sd:
        return

    # filter device
    if not device.address == button_mac:
        logging.info(f"Expected device mac {button_mac} but got {device.address}. Ignoring.")
        return

    sd = advertisement_data.service_data
    if service_uuid not in sd:
        return

    payload = sd[service_uuid]
    event = payload[-1]

    now = time.time()

    # EDGE TRIGGER: only first packet in burst
    if now - last_trigger_time < LOCKOUT:
        return

    last_trigger_time = now

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

    args = parser.parse_args()

    service_uuid = args.service_uuid or os.getenv("SERVICE_UUID", DEFAULT_SERVICE_UUID)
    button_mac_address = args.button_mac_address or os.getenv("BUTTON_MAC_ADDRESS")
    endpoints = {
        1: args.single_click_endpoint or os.getenv("SINGLE_CLICK_ENDPOINT"),
        2: args.double_click_endpoint or os.getenv("DOUBLE_CLICK_ENDPOINT"),
        4: args.long_click_endpoint or os.getenv("LONG_CLICK_ENDPOINT")
    }

    return (service_uuid, button_mac_address, endpoints)

def validate_arguments(button_mac_address, endpoints):
    if button_mac_address is None:
        print("Must provide --button-mac-address or env BUTTON_MAC_ADDRESS")
        exit(1)

    if all(value is None for value in endpoints.values()):
        print("A --single-click-endpoint or env SINGLE_CLICK_ENDPOINT, --double-click--endpoint or DOUBLE_CLICK_ENDPOINT, or --long-click-endpoint or LONG_CLICK_ENDPOINT is required")
        exit(1)


async def main():
    service_uuid, button_mac_address, endpoints = parse_arguments()
    validate_arguments(button_mac_address, endpoints)

    callback_partial = partial(callback, button_mac_address, service_uuid, endpoints)
    logging.info(f"Listening for button {button_mac_address} with service {service_uuid}, endpoints: {endpoints}")

    scanner = BleakScanner(callback_partial)
    await scanner.start()

    while True:
        await asyncio.sleep(1)

asyncio.run(main())
