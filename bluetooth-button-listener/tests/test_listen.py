"""
Pytest suite for bluetooth_button_listener.py's payload parsing.

Two ways to use this file:

1. Run it with pytest to check parsing against a set of known payloads
   (both real Shelly BLU1 payloads and the problematic ones pulled from
   your logs) with known expected outcomes:

       pip install pytest --break-system-packages   # if not already installed
       pytest test_bluetooth_button_listener.py -v

2. Capture real payloads from your own button and replay them for manual
   review — useful when you see something unexpected in the logs and want
   to check exactly how it decodes without waiting for it to happen again.

   Step 1 — capture some real traffic to a file:
       python3 bluetooth_button_listener.py \\
           --button-mac-address AA:BB:CC:DD:EE:FF \\
           --single-click-endpoint http://example/single \\
           --capture-payloads captured.jsonl
       # press the button a few times, Ctrl+C when done

   Step 2 — replay the capture and see how each payload decodes:
       python3 test_bluetooth_button_listener.py --replay captured.jsonl
"""

import sys
import json

import pytest

import btb.listen as bbl
from btb.listen import extract_button_event, parse_bthome, callback, DEFAULT_SERVICE_UUID


class FakeDevice:
    def __init__(self, address, name):
        self.address = address
        self.name = name


class FakeAdvertisementData:
    def __init__(self, service_data, rssi=-60):
        self.service_data = service_data
        self.rssi = rssi


def h(hexstr):
    """Shorthand: hex string -> bytes."""
    return bytes.fromhex(hexstr)


# ---------------------------------------------------------------------------
# Known payloads with known expected results.
#
# The "real click" samples are genuine Shelly BLU Button1 BTHome payloads
# (decoded from base64 examples of real button traffic). The "from your
# logs" samples are the exact idle/telemetry payloads that were previously
# triggering "Unexpected object ID" warnings.
# ---------------------------------------------------------------------------
KNOWN_CASES = [
    # (description, hex payload, expected battery, expected event)

    # --- Real single/double/triple/long click payloads ---
    ("real single click",  "4400e301643a01", 100, 1),
    ("real double click",  "4400e501643a02", 100, 2),
    ("real triple click",  "4400eb01643a03", 100, 3),
    ("real long click",    "4400ec01643a04", 100, 4),

    # --- Idle beacons between presses: button object present, value 0 ---
    ("idle beacon, no click",   "4400dd01643a00", 100, 0),
    ("idle beacon, no click 2", "4400ee01643a00", 100, 0),

    # --- Payloads captured from your actual logs: telemetry-only,
    #     no button object at all (these caused the false warnings) ---
    ("your log sample 1", "44009c0164f00102f100120001", 100, None),
    ("your log sample 2", "44009d0164f00102f100120001", 100, None),
    ("your log sample 3", "44009e0164f00102f100120001", 100, None),

    # --- Low battery, single click, to confirm battery isn't hardcoded ---
    # bytes: 44 (device info) 00 05 (pid=5) 01 0a (battery=10%) 3a 01 (single click)
    ("low battery single click", "440005010a3a01", 10, 1),

    # --- Payload with no battery object at all ---
    # bytes: 44 (device info) 00 05 (pid=5) 3a 01 (single click)
    ("no battery object, single click", "4400053a01", None, 1),
]

# ids= gives each case a readable name in pytest's output (e.g.
# test_known_payloads[real single click]) instead of a numeric index.
@pytest.mark.parametrize(
    "description, hexstr, expected_battery, expected_event",
    KNOWN_CASES,
    ids=[case[0] for case in KNOWN_CASES],
)
def test_known_payloads(description, hexstr, expected_battery, expected_event):
    result = extract_button_event(h(hexstr))
    assert result["battery"] == expected_battery, (
        f"[{description}] battery mismatch for payload {hexstr}"
    )
    assert result["event"] == expected_event, (
        f"[{description}] event mismatch for payload {hexstr}"
    )


def test_empty_payload():
    result = extract_button_event(h(""))
    assert result["event"] is None
    assert result["battery"] is None


def test_only_device_info_byte():
    # Just the leading device-info byte, no objects at all
    result = extract_button_event(h("44"))
    assert result["event"] is None
    assert result["battery"] is None


def test_truncated_object_value():
    # Claims object 0x01 (battery, 1-byte value) but payload ends right
    # after the object id, with no value byte
    result = extract_button_event(h("4401"))
    assert result["battery"] is None
    assert result["event"] is None


def test_unknown_object_stops_parsing_gracefully():
    # 0xff is not in BTHOME_OBJECT_LENGTHS — parsing should stop there
    # rather than raise, and anything after it (including a real button
    # object) is not seen. This documents the current "stop at first
    # unknown" behavior rather than a "skip and continue" behavior.
    payload = h("4400" + "9c" + "ff0102" + "3a01")
    result = extract_button_event(payload)
    assert result["event"] is None  # never reached the 3a object


def test_multiple_button_objects_last_one_wins():
    # Not expected in real traffic, but confirms parse_bthome walks the
    # whole payload rather than stopping at the first match.
    payload = h("4400" + "9c" + "3a01" + "3a02")
    objs = list(parse_bthome(payload))
    button_events = [v[0] for oid, v in objs if oid == 0x3A]
    assert button_events == [1, 2]


MAC = "AA:BB:CC:DD:EE:FF"
SERVICE_UUID = DEFAULT_SERVICE_UUID
ENDPOINTS = {1: "http://example/single", 2: "http://example/double", 4: "http://example/long"}


@pytest.fixture(autouse=True)
def reset_lockout_state():
    """
    callback() tracks click/telemetry lockouts in module-level globals, so
    without a reset, whichever test runs first "uses up" the lockout window
    for every test after it. Reset before each test for isolation.
    """
    bbl.last_trigger_time = 0
    bbl.last_telemetry_log_time = 0
    yield


def make_advertisement(payload_hex, rssi=-60):
    return FakeAdvertisementData(service_data={SERVICE_UUID: h(payload_hex)}, rssi=rssi)


def test_telemetry_only_payload_logs_battery(caplog):
    # A real payload from the logs: no button object, battery = 100%
    device = FakeDevice(MAC, "SBBT-002C")
    ad = make_advertisement("44009c0164f00102f100120001")

    with caplog.at_level("INFO"):
        callback(MAC, SERVICE_UUID, ENDPOINTS, None, device, ad)

    assert any(
        "Telemetry" in rec.message and "Battery: 100%" in rec.message
        for rec in caplog.records
    )


def test_telemetry_logging_is_rate_limited(caplog):
    device = FakeDevice(MAC, "SBBT-002C")
    ad = make_advertisement("44009c0164f00102f100120001")

    with caplog.at_level("INFO"):
        callback(MAC, SERVICE_UUID, ENDPOINTS, None, device, ad)
        caplog.clear()
        # Immediately repeat — simulates the ~30-packet burst seen in
        # real logs. Should NOT log again within TELEMETRY_LOG_LOCKOUT.
        callback(MAC, SERVICE_UUID, ENDPOINTS, None, device, ad)

    assert not any("Telemetry" in rec.message for rec in caplog.records)


def test_telemetry_without_battery_object_does_not_log(caplog):
    device = FakeDevice(MAC, "SBBT-002C")
    # pid object only, no battery, no button object
    ad = make_advertisement("440005")

    with caplog.at_level("INFO"):
        callback(MAC, SERVICE_UUID, ENDPOINTS, None, device, ad)

    assert not any("Telemetry" in rec.message for rec in caplog.records)


def test_real_click_still_triggers_not_logged_as_telemetry(caplog, monkeypatch):
    device = FakeDevice(MAC, "SBBT-002C")
    ad = make_advertisement("4400e301643a01")  # real single click

    # Avoid an actual outbound HTTP call — we only care that trigger()
    # was reached with the right event, not that the request succeeds.
    calls = []
    monkeypatch.setattr(
        bbl, "requests",
        type("FakeRequests", (), {"post": staticmethod(lambda *a, **k: calls.append((a, k)) or type("R", (), {"status_code": 200})())})()
    )

    with caplog.at_level("INFO"):
        callback(MAC, SERVICE_UUID, ENDPOINTS, None, device, ad)

    messages = [rec.message for rec in caplog.records]
    assert any("Event: 1" in m for m in messages)
    assert not any("Telemetry" in m for m in messages)
    assert len(calls) == 1
    assert calls[0][0][0] == "http://example/single"


# ---------------------------------------------------------------------------
# Replay mode: feed real captured payloads (from --capture-payloads) through
# the same parsing logic and print a readable summary for manual review.
# Not a pytest test itself (doesn't start with test_) — run directly instead:
#   python3 test_bluetooth_button_listener.py --replay captured.jsonl
# ---------------------------------------------------------------------------
def replay(path):
    print(f"{'timestamp':<20} {'mac':<18} {'battery':<8} {'event':<6} payload")
    print("-" * 90)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            payload = bytes.fromhex(entry["payload_hex"])
            result = extract_button_event(payload)
            print(
                f"{entry['ts']:<20.2f} "
                f"{entry['mac']:<18} "
                f"{str(result['battery']):<8} "
                f"{str(result['event']):<6} "
                f"{entry['payload_hex']}"
            )


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--replay":
        replay(sys.argv[2])
    else:
        print(
            "This file is a pytest suite. Run it with:\n"
            "    pytest test_bluetooth_button_listener.py -v\n"
            "Or replay a captured payload log with:\n"
            "    python3 test_bluetooth_button_listener.py --replay captured.jsonl"
        )