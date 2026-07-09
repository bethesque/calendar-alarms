#!/bin/bash

echo "Dev only, ensure the index.py server and mpd are running..."

curl -X POST http://127.0.0.1:8081/announce -d '{"message": "This is a one-off announcement test", "players": ["kaypi", "travcal"]}' -H "Content-Type: application/json"
sleep 5
curl -X POST "http://127.0.0.1:8081/announce?message=This+is+a+one-off+announcement+test&players=kaypi&players=travcal"
