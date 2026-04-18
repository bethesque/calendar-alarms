#!/bin/bash -e

for file in $(find logs -type f -name "*.log"); do
    echo "Rotating logs/$file"
    /usr/bin/tail -n 500 "logs/$file" > "logs/$file.tmp"
    /bin/mv "logs/$file.tmp" "logs/$file"
done
