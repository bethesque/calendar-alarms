#!/bin/bash

ANSIBLE_FORCE_COLOR=true  ansible-playbook -i ansible/inventory/hosts.yml --limit audio_host \
    ansible/audio_host.yml -e @ansible/secrets.yml "$@" \
    2>&1 | ts '[%Y-%m-%d %H:%M:%S]'

