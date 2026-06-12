import asyncio
from bleak import BleakScanner

def callback(device, advertisement_data):
    if not device.name or not device.name.startswith("SBBT"):
        return

    mfg = advertisement_data.manufacturer_data.get(2985)

    if not mfg:
        return

    payload = list(mfg)

    print(payload)

async def main():
    scanner = BleakScanner(callback)
    await scanner.start()

    while True:
        await asyncio.sleep(1)

asyncio.run(main())
