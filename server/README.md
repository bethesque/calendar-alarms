# Calendar Alarms Server

Plays announcements and alarms for calendar events sourced from Google Calendar using Snapcast to stream the audio. Reads a daily summary of events in the morning. Plays alarms and announcements for events with `#alarm` or `#announce` in the description.

## Development

### Requirements

Mac or Linux environment. Windows is not supported.

- python 3.13 or later
- mpd (music player for mac/linux) and mpc (the client)
- snapcast (a multiroom client-server audio player)
- ffmpeg (used to mix announcements and alarm music)
- ansible

### Set up

#### mac

```
python -m venv .venv
source .venv/bin/activate
pip install -e .
brew install mpd
brew install mpc
brew install snapcast
brew install ffmpeg
```

In `~/.mpd/mpd.conf` set `bind_to_address		"/tmp/mpd.socket"`
In shell set

```shell
export MPD_HOST = "/tmp/mpd.socket"
export MPD_PORT = 0
```

#### linux
```
python -m venv .venv
source ./venv/Scripts/activate
pip install -e .
sudo apt install mpd
sudo apt install mpc
sudo apt install snapcast
sudo apt install ffmpeg
```

### Automated testing

```
python3 -m pip install -e ".[dev]"
pytest
```

### Local manual testing

For mac, in `vcal/env.py` set

```py
MPD_HOST = "/tmp/mpd.socket"
MPD_PORT = 0
```

Ensure MPD daemon is running

```
/opt/homebrew/opt/mpd/bin/mpd --no-daemon --verbose
```

Run scripts in `/tests/manual`

To stop the audio:
```
export MPD_HOST="/tmp/mpd.socket"
mpc stop
```
