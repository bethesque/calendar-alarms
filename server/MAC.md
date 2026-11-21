# Snapcast as a macOS LaunchAgent

## Install

```bash
brew install snapcast
which snapclient
```

## Create the plist

```bash
cat > ~/Library/LaunchAgents/com.snapcast.snapclient.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.snapcast.snapclient</string>

    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/snapclient</string>
        <string>tcp://nas.dixon.net.au:1704</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>/Users/beth/Library/Logs/snapclient.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/beth/Library/Logs/snapclient.log</string>
</dict>
</plist>
EOF
```

## Enable and start

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.snapcast.snapclient.plist
```

## Restart

```bash
launchctl kickstart -k gui/$(id -u)/com.snapcast.snapclient
```

## Stop and disable

```bash
launchctl bootout gui/$(id -u)/com.snapcast.snapclient
```

## Status

```bash
launchctl print gui/$(id -u)/com.snapcast.snapclient
```

## Logs

```bash
tail -f ~/Library/Logs/snapclient.log
```

## Reload after editing the plist

```bash
launchctl bootout gui/$(id -u)/com.snapcast.snapclient
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.snapcast.snapclient.plist
```
