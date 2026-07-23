#!/bin/bash

ANSIBLE_FORCE_COLOR=true ansible-playbook -i ansible/inventory/hosts.yml \
    --limit audio_clients ansible/debug_audio_clients.yml \
    -e @ansible/secrets.yml "$@"