import asyncio
from bleak import BleakScanner

async def main():
    while True:
        devices = await BleakScanner.discover(timeout=5)

        print("---- scan ----")

        for d in devices:
            print(d)

asyncio.run(main())