#!/bin/bash

ANSIBLE_FORCE_COLOR=true  ansible-playbook -i ansible/inventory/hosts.yml \
    --limit bluetooth_button_listeners ansible/bluetooth_button_listeners.yml \
    -e @ansible/secrets.yml "$@" \
    2>&1 | ts '[%Y-%m-%d %H:%M:%S]'
