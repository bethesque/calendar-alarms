#!/bin/bash

ansible-playbook -i ansible/inventory/hosts.yml --limit bluetooth_button_listeners ansible/bluetooth_button_listeners.yml -e @ansible/secrets.yml "$@"
