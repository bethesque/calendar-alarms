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
```


# Useful links

https://github.com/snapcast/snapcast/issues/1094

