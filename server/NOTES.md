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