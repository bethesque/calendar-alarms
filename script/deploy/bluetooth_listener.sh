#!/bin/bash

ansible-playbook -i ansible/inventory/hosts.yml --limit bluetooth_listeners ansible/bluetooth_listeners.yml -e @ansible/secrets.yml "$@"
