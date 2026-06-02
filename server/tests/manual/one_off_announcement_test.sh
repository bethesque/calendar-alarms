#!/bin/bash

echo "Dev only, ensure the index.py server and mpd are running..."

curl -X POST http://127.0.0.1:8081/announce?message=This%20is%20a%20one-off%20announcement%20test -H "Content-Length:0"
