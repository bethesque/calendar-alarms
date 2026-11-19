#!/bin/bash

ANSIBLE_FORCE_COLOR=true  ansible-playbook -i ansible/inventory/dwain_hosts.yml --limit audio_clients \
    ansible/audio_clients.yml -e @ansible/secrets.yml "$@" \
    2>&1 | ts '[%Y-%m-%d %H:%M:%S]'
