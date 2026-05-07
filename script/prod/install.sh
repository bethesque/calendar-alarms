python3 -m pip install -e "."
sudo systemctl restart calendar-alarms-http.service
sleep 5
sudo systemctl status calendar-alarms-http.service

