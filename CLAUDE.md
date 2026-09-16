# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

House-wide audio system: plays alarms/announcements sourced from Google Calendar, streamed over Snapcast to multiple rooms. Physical/IoT: **server** runs on a Pi or Mac; **client** runs on each room's Pi, driving a speaker via Snapclient; **bluetooth-button-listener** runs on a Pi Zero W paired with a Shelly BLU button to stop/toggle audio.

There are three independent Python projects, each with its own venv and `pyproject.toml`:

- `server/` — reads Google Calendar, generates TTS, mixes with music, drives Snapcast/MPD. Also a small FastAPI admin UI.
- `client/` — FastAPI service; mutes/unmutes ALSA and local Snapclient on bluetooth button presses, reports status.
- `bluetooth-button-listener/` — decodes BLE clicks from a Shelly BLU button, POSTs to the client's endpoints.

Supporting dirs: `ansible/` (deploy playbooks/roles), `script/` (cron wrappers, deploy scripts), `snapweb/` (prebuilt Snapweb frontend, not built from source — see `fe9aa68`).

## Commands

### server/

```
cd server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                        # full suite
pytest tests/vcal/calendar/test_google_calendar.py       # one file
pytest tests/vcal/calendar/test_google_calendar.py::TestName::test_it  # one test
```

Requires `mpd`, `mpc`, `snapcast`, `ffmpeg` (see `server/README.md`). Manual integration scripts: `server/tests/manual/*.sh` (run directly, not via pytest).

Entry points (`server/pyproject.toml`): `cal-alarm-check` / `cal-alarm-stop` / `cal-alarm-test` / `cal-announce` / `cal-school-announce` / `cal-data-refresh` / `cal-data-insert-test`.

Run admin server locally: `python index.py` (from `server/`, reads `config/uvicorn.yaml`). In production, notification checking/playback runs continuously as a daemon (`calendar_alarms_daemon.py`, systemd `calendar-alarms.service`), not via cron.

### client/

```
cd client
python -m venv .venv && source .venv/bin/activate
pip install -e .
script/start.sh
```

No test suite for this project.

### bluetooth-button-listener/

```
cd bluetooth-button-listener
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest tests/test_listen.py
```

Can run directly with `--replay <captured.jsonl>` against `btb/listen.py` to debug BLE payloads without a live button.

### Deployment

Via Ansible from a dev machine (requires `ansible` + `ts` from moreutils on macOS):
```
script/deploy/audio_host.sh       # server
script/deploy/audio_clients.sh    # room clients
script/deploy/bluetooth_button_listener.sh
```
`ansible/secrets.yml` (gitignored, create locally) needs `travnas_pass`, `pi_pass`, `travnas_ssh_public_key`.

## Architecture

Server code lives under `server/homeaudio/` (`homeaudio.vcal.*`, `homeaudio.audio.*`, `homeaudio.housie_talkie.*`); older docs/scripts may still say `vcal/` for the pre-restructure layout.

### homeaudio/vcal — core domain logic

- **`vcal/cal/google_calendar.py`** — fetches/caches Calendar events (`calendar.json`, dataclasses not pydantic). `Event.notifications()`/`notifications_within_window()` scan descriptions for `#alarm`/`#alarm<N>`/`#announce`/`#announce<N>` tags plus rule-based notifications from settings.
- **`vcal/event_notifications/`** (`core.py`, `events.py`, `audio.py`, `text.py`, `snooze.py`) — `NotificationFinder` (events.py) buckets due calendar-driven events. `AlarmAudio`/`AnnouncementAudio` (audio.py) build playable files: TTS (`text_to_voice.py`/gTTS) mixed with music (`homeaudio/audio/sound.py`, shells to ffmpeg), looped per `AlarmSettings`. `snooze.py` persists last-played/snooze state to file.
- **`vcal/morning_announcements/core.py`** / **`vcal/school_announcements/core.py`** — scheduled daily summaries; each exposes `check_for_announcement()` and is checked by the daemon alongside event notifications.
- **`vcal/core.py`** — orchestration glue: `prepare_notification_files()`/`play_notification_files()` combine event notifications + morning + school announcements into one `NotificationFiles`; also `stop_alarm()`, `snooze_alarm()`, `test_alarm()`.
- **`vcal/daemon.py`** — `NotificationCheckDaemon`, the long-running process (`calendar_alarms_daemon.py`, systemd `calendar-alarms.service`) that replaces the old 5-min cron: sleeps until the next check/announcement boundary (`notification_schedule.py`), prepares audio ahead of time, then plays it. Also starts `calendar_refresh.py`'s `CalendarRefreshLoop` (calendar data is no longer refreshed by cron).
- **`vcal/wake_up_alarm/`** — standalone wake-up alarm (random file from `WAKE_UP_ALARMS_DIRECTORY`), independent of the calendar flow but shares MPD/Snapcast.

### homeaudio/audio — playback/device plumbing (shared by vcal and housie_talkie)

- **`audio/scene.py`** — `SceneProtocol`, `NullScene`, `HomeAssistantScene`; `scene_for_env()` picks one. Pauses/dips Music Assistant players before an alarm/announcement and restores after; state persisted to a file since `restore_after_alarm()` (a `@staticmethod`) runs from a separate process.
- **`audio/snapcast.py` / `audio/snapserver.py`** — wraps the Snapserver JSON-RPC API. Volumes per-usecase (`tts`/`voice`/`alarm`) and per-room (`SnapclientConfig.area`), configured in `config/snapcast.yaml`.
- **`audio/mpd.py`** — wraps `python-musicpd`, with fade-up/fade-out helpers.
- **`audio/settings.py`** — all settings classes (see below). **`audio/admin_ui.py`** — the admin UI. **`audio/logs_ui.py`** — log/journalctl viewer routes.

### homeaudio/housie_talkie — voice-message intercom

Shares the MPD/Snapcast/Scene plumbing above (`core.py` reuses `scene_for_env()` and the Snapserver wrapper like `vcal/core.py` does). Also has its own `cli.py`, `models.py`, `ui.py`, `voice.py` / `voice_api.py` / `voice_ffmpeg.py`, `tts_api.py`.

### Settings (`homeaudio/audio/settings.py`)

Each settings group is a `pydantic_settings.BaseSettings` (`YAMLSettings` subclass) backed by a YAML file under `server/config/` (`main.yaml`, `mpd.yaml`, `snapcast.yaml`, `google_calendar.yaml`, `morning_announcements.yaml`, `school_announcements.yaml`, `home_assistant.yaml`, `housie_talkie.yaml`, `notifications.yaml`). `YAMLSettings.save()` writes back for settings with mutable runtime state (e.g. "last used" timestamps). `AppSettings` aggregates all groups for the admin UI.

### Entry points and process boundaries

`server/index.py` is the always-on FastAPI app (systemd `calendar-alarms-http.service`): admin UI, Google OAuth callback, log viewers, HTTP endpoints like alarm-stop. `calendar_alarms_daemon.py` (systemd `calendar-alarms.service`) is the separate long-running process that actually checks for and plays notifications/announcements and refreshes calendar data — it is *not* run inside the FastAPI process. `check_for_alarms.py` / `morning_announcements.py` remain as one-shot scripts (`cal-alarm-check` / `cal-announce`) for manual/test use. This split matters: anything that needs to affect a currently-playing alarm from the HTTP server (e.g. stopping it, restoring Music Assistant state) has to work via shared files/state rather than in-memory objects, since it's a different process.

### client/ (per-room audio control)

`client/index.py` exposes `/audio/toggle` and `/audio/stop`, triggered by the bluetooth listener's POSTs. Mutes ALSA immediately (`amixer_control.py`), then asynchronously mutes the local Snapclient (`snapserver.py`) or pauses/toggles Music Assistant via a Home Assistant webhook (`music_assistant.py`), depending on what's playing. Runs in a background thread with a non-blocking lock (`_operation_lock`) so overlapping presses return `409`.

### bluetooth-button-listener/

`btb/listen.py` uses `bleak` to scan for one Shelly BLU button (by MAC), decodes the BTHome v2 TLV payload for click type/battery, POSTs to `SINGLE_CLICK_ENDPOINT`/`DOUBLE_CLICK_ENDPOINT`/`LONG_CLICK_ENDPOINT` (normally a `client/` instance's `/audio/*` routes). `parse_bthome`/`extract_button_event` are pure, unit-tested against captured payloads; the test file also works as a replay tool (`--replay captured.jsonl`).

# Guidelines

Do not rename any functions unless instructed to.
Keep code comments to 1 sentence.
Do not add mulitple sentence comments explaining why a piece of code does something a certain way. You do not need to explain exception handling logic in the comments. Developers understand exception handling.

# Testing

Use pytest, not unittest.

The tests for any file should be under the module path with "tests/" prepended to the module path and "test_" at the start of the base name of the file. eg. foo/bar.py should have a test at tests/foo/test_bar.py. The exception to this is where there is a pytest conflict due to test file names being the same (eg. core_test.py ) in which case an appropriate differentiator may be included in the file name.


## Deployments

In the original deployment ("Tortice Home Audio"), the Ansible role calendar_alarms_server runs on a Linux NAS (travnas) and the Ansible roles calendar_alarms_client and music_assistant_client run on single core Raspberry Pi Zero W (kaypi, patpi, officepi and travcal) as well as the NAS.

In the Tortice deployment, the notifications are checked and played every 1 minute, as the NAS is well resourced and can generate the notification audio in under 15 seconds.

In a second deployment for Dwain, called Ferny Home Audio, the calendar_alarms_server role is deployed to a single Raspberry Pi Zero W. It plays the audio over MPD which plays directly to a speaker - there is no Snapcast integration. The calendar_alarms_client and music_assistant_client roles are not used in this deployment.

In the Ferny deployment, the notifications are checked every 5 minutes, as the ffmpeg code takes about a minute to run to prepare the notification audio on the low-resourced Raspberry Pi.
