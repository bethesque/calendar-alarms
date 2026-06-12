import asyncio
from bleak import BleakScanner

def callback(device, advertisement_data):
    if not device.name or not device.name.startswith("SBBT"):
        return

    print("DEVICE:", device.name)
    print("ADDR:", device.address)
    print("RSSI:", advertisement_data.rssi)
    print("MFG:", advertisement_data.manufacturer_data)
    print("---")

async def main():
    scanner = BleakScanner(callback)
    await scanner.start()

    while True:
        await asyncio.sleep(1)

asyncio.run(main())
