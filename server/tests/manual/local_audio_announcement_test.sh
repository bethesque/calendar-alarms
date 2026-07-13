#!/bin/bash

echo "Dev only, ensure the index.py server and mpd are running..."

curl -X POST http://localhost:8081/talkie \
  -F "players=travcal" \
  -F "sound_effect=none" \
  -F "audio=@tests/manual/recording_1783930884421.m4a"
