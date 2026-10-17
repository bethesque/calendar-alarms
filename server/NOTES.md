# Useful commands

```
aplay --dump-hw-params -D usb_hw /usr/share/sounds/alsa/Front_Center.wav
Playing WAVE '/usr/share/sounds/alsa/Front_Center.wav' : Signed 16 bit Little Endian, Rate 48000 Hz, Mono
HW Params of device "usb_hw":
--------------------
ACCESS:  MMAP_INTERLEAVED RW_INTERLEAVED
FORMAT:  S16_LE
SUBFORMAT:  STD MSBITS_MAX
SAMPLE_BITS: 16
FRAME_BITS: 32
CHANNELS: 2
RATE: [44100 48000]
PERIOD_TIME: [1000 1000000]
PERIOD_SIZE: [45 48000]
PERIOD_BYTES: [180 192000]
PERIODS: [2 1024]
BUFFER_TIME: [1875 2000000]
BUFFER_SIZE: [90 96000]
BUFFER_BYTES: [360 384000]
TICK_TIME: ALL
--------------------
aplay: set_params:1398: Channels count non available
```

```
curl -X POST http://nas.dixon.net.au:1780/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"id":1,"jsonrpc":"2.0","method":"Server.GetStatus"}' | jq .
```

```
# Test Snapserver without MPD
aplay -D plughw:0,0,0 /usr/share/sounds/alsa/Front_Center.wav
```


Sendspin on NAS

sudo apt install build-essential cmake git pkg-config \
  libasound2-dev portaudio19-dev libavahi-compat-libdnssd-dev

git clone https://github.com/Sendspin/sendspin-cpp-cli.git
cd sendspin-cpp-cli
git checkout v0.3.0
rm -rf build
cmake -B build -DCMAKE_INSTALL_PREFIX=/usr/local


cmake --build build -j2

./build/sendspin-cli -o plughw:CARD=Device,DEV=0 \
  --server ws://nas.dixon.net.au:8927/sendspin

sudo cmake --install build --component sendspin-cli

sudo cp /usr/local/share/doc/sendspin-cli/sendspin-cli.conf.example /etc/sendspin-cli.conf

vi ~/.config/systemd/user/sendspin-cli.service
```
[Unit]
Description=Sendspin Audio Player
StartLimitIntervalSec=120
StartLimitBurst=5

[Service]
ExecStart=/usr/local/bin/sendspin-cli --config /etc/sendspin-cli.conf
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

# update values in sendspin-cli.conf

systemctl --user daemon-reload
systemctl --user enable --now sendspin-cli
journalctl --user -u sendspin-cli -f
