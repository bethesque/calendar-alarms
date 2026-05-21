# Google calendar alarms



## Deployment

### Requirements

- A Raspberry Pi or other Linux like environment to run the python scripts and Snapserver on. I had trouble getting the pipes to work with Snapcast on Mac, so there may be some issue there.
- A speaker for every room you want the alarms to play in
- A Raspberry Pi or old Android phone for every speaker

### Installation

### Server

*Install python (instructions for Ubuntu jammy)*

```
# Update python
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13
sudo apt install python3.13-venv
python3.13 -m ensurepip --upgrade
python3.13 -m pip install --upgrade pip setuptools wheel
```

*Clone and set up repository*
```
git clone https://github.com/bethesque/calendar-alarms.git
cd calendar-alarms
sudo apt install python3-pip
python3.13 -m pip install -e .
```

*Set up users/packages/service*

On develoment machine
1. Install ansible.
1. Create `ansible/secrets.yml` with:
    * `travnas_pass`
    * `pi_pass`
1. Run `script/deploy/audio_host.sh`
1. Run `script/deploy/audio_clients.sh`

#### HTTP service

The HTTP service provides two functions - allowing the calendar to get/update Google credentials for fetching the calendar data, and providing an endpoint to stop the alarm.

```

sudo cp /home/beth/calendar-alarms/calendar-alarms-http.service /lib/systemd/system/calendar-alarms-http.service
```

Reload with:

```
sudo systemctl daemon-reload
```

Start service if it has stopped with

```
sudo systemctl restart calendar-alarms-http.service
```

View system logs using

```
journalctl -u calendar-alarms-http -f # view logs
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
export SNAPCLIENT_NAME="vcal" # give your client a unique name
echo "SNAPCLIENT_OPTS=\"-h ${SNAPSERVER_IP} --soundcard pulse --hostID=${SNAPCLIENT_NAME}\"" | sudo tee /etc/default/snapclient > /dev/null
cat /etc/default/snapclient # sanity check

sudo systemctl restart snapclient

journalctl -u snapclient -f # view logs
cat /lib/systemd/system/snapclient.service # view systemd config file

```

# Useful links

https://github.com/snapcast/snapcast/issues/1094
https://whynot.guide/posts/howtos/multiroom-media/
https://www.hietala.org/multi-room-audio-with-mpd-and-snapcast.html
https://www.instructables.com/From-Record-Player-to-Multi-room-Spotify-Controler/
https://berthaamelia.github.io/blog/python/raspberrypi/2020/08/20/connect-bluetooth-speaker-to-raspi-zero.html
https://community.home-assistant.io/t/perfect-and-free-synchronous-multiroom-audio-with-snapcast/386871




