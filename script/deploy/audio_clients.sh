#!/bin/bash

ansible-playbook -i ansible/inventory/hosts.ini --limit audio_clients ansible/site.yml --ask-become-pass
