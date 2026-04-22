#!/bin/bash

ansible-playbook -i ansible/inventory/hosts.ini ansible/site.yml --ask-become-pass
