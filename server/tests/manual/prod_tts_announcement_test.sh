#!/bin/bash

curl -X POST http://nas.dixon.net.au:8442/announce -d '{"message": "This is a one-off announcement test"}' -H "Content-Type: application/json"
