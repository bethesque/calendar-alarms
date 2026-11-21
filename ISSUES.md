# Snapclient audio buffer underun errors

Sep 06 09:07:16

sudo apt install cpufrequtils   # if not already installed
echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils
sudo systemctl restart cpufrequtils

watch -n 0.2 cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq


Wed 9 Sep 8:20am
sudo nmcli connection modify netplan-wlan0-thetravsnbn 802-11-wireless.bssid f8:ca:59:a8:94:35
sudo nmcli connection up netplan-wlan0-thetravsnbn

Think I picked the wrong AP, try the other one



sudo nmcli connection modify netplan-wlan0-thetravsnbn 802-11-wireless.bssid d0:db:b7:49:d8:48
sudo nmcli connection up netplan-wlan0-thetravsnbn


# SSH dropping occasionally

## keep the journal logs
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo systemctl restart systemd-journald


sudo mkdir /etc/systemd/journald.conf.d/
sudo vi /etc/systemd/journald.conf.d/override.conf

[Journal]
Storage=persistent
SystemMaxUse=200M



## turn off wifi power management
pi@travcal:~ $ sudo tee /etc/systemd/system/wifi-powersave-off.service > /dev/null <<'EOF'
[Unit]
Description=Disable WiFi power management
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/iwconfig wlan0 power off

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now wifi-powersave-off.service



# PLN

Reinstall everything from scratch without music assistant
Use hw directly



Oct 02 08:03:34 travcal calendar-alarms-snapclient[9161]: 2026-10-02 08-03-34.471 [Error] (Alsa) Exception in initAlsa: Can't open plughw:Device,0, error: Device or resource busy
^C
pi@travcal:~ $ sudo fuser -v /dev/snd/*
[sudo] password for pi:
                     USER        PID ACCESS COMMAND
/dev/snd/pcmC0D0p:   pi          983 F...m sendspin-armv6
/dev/snd/timer:      pi          983 f.... sendspin-armv6

