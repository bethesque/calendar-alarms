#!/bin/bash

ansible-playbook -i ansible/inventory/hosts.yml --limit audio_clients ansible/audio_clients.yml -e @ansible/secrets.yml "$@" 2>&1 | ts '[%H:%M:%S]'
