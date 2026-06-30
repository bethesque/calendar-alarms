python3 -m pip install -e "."
systemctl --user restart calendar-alarms-http.service
sleep 5
systemctl --user status calendar-alarms-http.service

