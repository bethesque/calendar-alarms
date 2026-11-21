[x] copy sound effects
[x] copy alarms
[x] upload API key
[] password hide
[x] move config out of src directory
[x] accents in settings
[ ] duplicates
[x] fix settings attributes not dynamically updating
[x] notifications for past morning events


## Calendars

https://www.vic.gov.au/sites/default/files/2026-01/Victorian-public-holiday-dates.ics



https://theweatherchaser.com/forecasts/ics/086266.ics

https://theweatherchaser.com/forecasts/ics/86081-mount-dandenong.ics

# Setting up Raspberry Pi 4

## Disable nginx

```
sudo systemctl stop nginx
sudo systemctl disable nginx
```

## Make sure the services have started

Not sure why these just don't work automatically.

```
sudo sysctl --system # to make sure the port 80 priv applied
systemctl --user enable calendar-alarms
systemctl --user enable calendar-alarms-http
systemctl --user start calendar-alarms
systemctl --user start calendar-alarms-http
```

Reboot after connecting speaker

## Set up wifi
```
ssh bigpi

# Check that NetworkManager is in use (should print "running")
nmcli general status

export FERNY_SSID=""
export FERNY_PASSWORD=""

# Add the Ferny Creek network without switching to it
sudo nmcli connection add type wifi con-name ferny ifname wlan0 \
  ssid "$FERNY_SSID" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$FERNY_PASSWORD" \
  connection.autoconnect yes connection.autoconnect-priority 10

# Check it saved, and see your existing home profile
nmcli -f NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show

sudo nmcli -s -g 802-11-wireless.ssid,802-11-wireless-security.psk connection show ferny
```

## Migrating from Pi Zero


```
ssh dwainpi
tar -czf calendar-alarms-resources.tar.gz calendar-alarms-resources
# exit
```

```
scp pi@dwainpi:/home/pi/calendar-alarms-resources.tar.gz .
scp calendar-alarms-resources.tar.gz pi@bigpi:/home/pi/calendar-alarms-resources.tar.gz
```

```
ssh bigpi
mv calendar-alarms-resources calendar-alarms-resources-bak
tar -xzf calendar-alarms-resources.tar.gz
cp calendar-alarms-resources-bak/config/snapcast.yaml calendar-alarms-resources/config/snapcast.yaml
```

```
vi /home/pi/calendar-alarms/server/homeaudio/env.py
# SNAPCAST_ENABLED = True
# NOTIFICATIONS_CHECK_INTERVAL_MINUTES = 1

```