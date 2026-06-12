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

Make sure a speaker is plugged in when deploying, or the snapclient services won't start.

On mac, install:
* ansible
* ts (`brew install moreutils`)

```shell
script/deploy/audio_clients.sh
```

First time, it might time out waiting for the reboot. Start the script again.


```
[Error] (Alsa) Exception: Can't open sysdefault, error: Unknown error 524, code: -524
```

Rebooting with the speaker plugged in and starting again seems to fix this problem.

# Useful links

https://github.com/snapcast/snapcast/issues/1094
https://whynot.guide/posts/howtos/multiroom-media/
https://www.hietala.org/multi-room-audio-with-mpd-and-snapcast.html
https://www.instructables.com/From-Record-Player-to-Multi-room-Spotify-Controler/
https://berthaamelia.github.io/blog/python/raspberrypi/2020/08/20/connect-bluetooth-speaker-to-raspi-zero.html
https://community.home-assistant.io/t/perfect-and-free-synchronous-multiroom-audio-with-snapcast/386871




