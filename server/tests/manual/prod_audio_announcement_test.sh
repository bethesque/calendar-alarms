#!/bin/bash

curl -X POST https://nas.dixon.net.au:8443/talkie -k \
  -F "players=travcal" \
  -F "sound_effect=none" \
  -F "audio=@tests/manual/recording_1783930884421.m4a"
