# Snapclient audio buffer underun errors

Sep 06 09:07:16

sudo apt install cpufrequtils   # if not already installed
echo 'GOVERNOR="performance"' | sudo tee /etc/default/cpufrequtils
sudo systemctl restart cpufrequtils

watch -n 0.2 cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq


Wed 9 Sep 8:20am
sudo nmcli connection modify netplan-wlan0-thetravsnbn 802-11-wireless.bssid f8:ca:59:a8:94:35
sudo nmcli connection up netplan-wlan0-thetravsnbn
