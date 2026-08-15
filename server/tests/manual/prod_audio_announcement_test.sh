#!/bin/bash

curl -X POST http://nas.dixon.net.au:8442/talkie \
  -F "players=kaypi" \
  -F "players=patpi" \
  -F "sound_effect=none" \
  -F "audio=@tests/manual/recording_1783930884421.m4a"
