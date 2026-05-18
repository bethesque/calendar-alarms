#!/bin/bash

ansible-playbook -i ansible/inventory/hosts.yml --limit audio_host ansible/audio_host.yml -e @ansible/secrets.yml "$@"
