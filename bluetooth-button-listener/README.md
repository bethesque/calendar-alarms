# Bluetooth button

Allows a Raspberry Pi Zero W to act as a hub for the Shelly BLU Button Tough 1.

Listens for single, double and long click events, and sends an HTTP POST request to the configured endpoints based on the click type.

## Installation on Raspberry Pi

On development machine:
```
script/deploy/copy_to_pi.sh
```

On pi:

```
sudo rfkill unblock bluetooth

sudo apt install python3-pip -y

cd /home/pi/bluetooth-button
python3 -m venv .venv
source .venv/bin/activate

.venv/bin/pip install . # this will take about 30 minutes
```

Environment variables:

```
BUTTON_MAC_ADDRESS="2A29D152-F572-30A8-DADA-ADAC88736594"
SINGLE_CLICK_ENDPOINT="http://0.0.0.0:8080/audio/toggle"
DOUBLE_CLICK_ENDPOINT=
LONG_CLICK_ENDPOINT=
LOG_LEVEL=info
BLEAK_LOG_LEVEL=warning
HTTP_LOG_LEVEL=0 # 0 for disabled or 1 for enabled
```

Start listening:
```
.venv/bin/python btb/listen.py
```

## Building the wheel

On dev machine:
```shell
cd bluetooth-button
script/deploy/copy_to_pi.sh
```

On raspberry pi:
```shell
cd /home/pi/bluetooth-button
python3 -m venv buildenv
source buildenv/bin/activate
pip install --upgrade pip setuptools wheel build
python -m build --wheel --outdir wheelhouse # This will take 30+ minutes
```

On dev machine:

```shell
dist
```

