# Google calendar alarms

## Development

### Requirements

Mac or Linux environment. Windows is not supported.

- python 3.13
- mpv (music player for mac/linux)
- snapcast (a multiroom client-server audio player)
- ffmpeg

### Set up

#### mac

```
python -m venv .venv
source .venv/bin/activate
pip install -e .
brew install mpv
brew install snapcast
brew install ffmpeg
```

#### linux
```
python -m venv .venv
source ./venv/Scripts/activate
pip install -e .
sudo apt install mpv
sudo apt install snapcast
sudo apt install ffmpeg
```

## Deployment

### Requirements

- A Raspberry Pi or other Linux like environment to run the python scripts and Snapserver on. I had trouble getting the pipes to work with Snapcast on Mac, so there may be some issue there.
- A speaker for every room you want the alarms to play in
- A Raspberry Pi or old Android phone for every speaker

### Installation

### Server
```
# Update python
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13
sudo apt install python3.13-venv
python3.13 -m ensurepip --upgrade
python3.13 -m pip install --upgrade pip setuptools wheel

git clone https://github.com/bethesque/calendar-alarms.git
cd calendar-alarms
sudo apt install python3-pip
sudo apt install mpv
brew install snapcast
sudo apt install ffmpeg
python3.13 -m pip install -e .

sudo usermod -aG audio $USER

# logout and login again

sudo apt install alsa-utils

# Step 1: enable loopback device
sudo modprobe snd-aloop

# Persist it
echo "snd-aloop" | sudo tee -a /etc/modules


vi /etc/snapserver.conf


```

### Clients

```
sudo apt install pipewire pipewire-audio pipewire-pulse wireplumber

# reboot (don't know why, just following what chatgpt says)

# connect to bluetooth device (follow script/connect_bluetooth_speaker.sh)

# Test audio
pw-play /usr/share/sounds/alsa/Front_Center.wav

# OR try
paplay /usr/share/sounds/alsa/Front_Center.wav


sudo apt install snapcast
sudo systemctl start snapclient
sudo systemctl enable snapclient # enable at startup


export SNAPSERVER_IP="192.168.20.3" # use your own server's IP here
export SNAPCLIENT_NAME="ecal" # give your client a unique name
echo "SNAPCLIENT_OPTS=\"-h ${SNAPSERVER_IP} --soundcard pulse --hostID=${SNAPCLIENT_NAME}\"" | sudo tee /etc/default/snapclient > /dev/null
cat /etc/default/snapclient # sanity check

sudo systemctl restart snapclient

journalctl -u snapclient -f # view logs
cat /lib/systemd/system/snapclient.service # view systemd config file

```

# Useful links

https://github.com/snapcast/snapcast/issues/1094



[Unit]
Description=Snapcast client
Documentation=man:snapclient(1)
Wants=avahi-daemon.service
After=network.target time-sync.target sound.target avahi-daemon.service
#
[Service]
EnvironmentFile=-/etc/default/snapclient
Environment=XDG_RUNTIME_DIR=/run/user/1000
ExecStart=/usr/bin/snapclient --logsink=system $SNAPCLIENT_OPTS
User=thetrav
Group=thetrav
# very noisy on stdout
StandardOutput=null
Restart=on-failure
#
[Install]
WantedBy=multi-user.target


echo '{ "command": ["loadfile", "/home/beth/calendar-alarms/cache/audio/daily_summary.mp3", "replace"] }'  | socat - /tmp/mpv_mixed.sock




mpv --idle=yes --no-video --keep-open=yes --ao=pcm --ao-pcm-file=/tmp/snapfifo --ao-pcm-waveheader=no --audio-format=s16 --audio-channels=stereo --audio-samplerate=48000 --input-ipc-server=/tmp/mpv_mixed.sock &

# this works
echo '{ "command": ["loadfile", "/home/beth/calendar-alarms/alarm_mix.wav"] }'  | socat - /tmp/mpv_mixed.sock

echo '{ "command": ["get_property", "idle-active"] }' | socat - /tmp/mpv_mixed.sock
# {"data":false,"request_id":0,"error":"success"}

# this does nothing
echo '{ "command": ["loadfile", "/home/beth/calendar-alarms/alarm_mix.wav"] }'  | socat - /tmp/mpv_mixed.sock
