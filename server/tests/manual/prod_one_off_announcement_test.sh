#!/bin/bash

curl -X POST https://nas.dixon.net.au:8443/announce -d '{"message": "This is a one-off announcement test"}' -H "Content-Type: application/json"