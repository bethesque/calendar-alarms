#!/bin/bash

ansible-playbook -i ansible/inventory/hosts.ini --limit audio_host ansible/site.yml --ask-become-pass
