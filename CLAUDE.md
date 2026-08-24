# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A house-wide audio system that plays alarms and announcements sourced from Google Calendar events, streamed over Snapcast to multiple rooms. It's a physical/IoT project: a Raspberry Pi (or Mac, for dev) runs the **server**, and a Raspberry Pi in each room runs the **client**, driving a speaker via Snapclient. One of the Raspberry Pi Zeros can run the **bluetooth-button-listener** to let a physical Shelly BLU button stop/toggle audio.

There are three independent Python projects, each with its own venv and `pyproject.toml`:

- `server/` — the brain. Reads Google Calendar, decides what to announce/alarm, generates TTS audio, mixes it with music, and tells Snapcast/MPD to play it. Also serves a small FastAPI admin UI.
- `client/` — runs on each room's Raspberry Pi. A small FastAPI service that mutes/unmutes ALSA output and the local Snapclient in response to bluetooth button presses, and reports status.
- `bluetooth-button-listener/` — runs on a Pi Zero W paired with a Shelly BLU Button Tough 1. Listens for BLE advertisements, decodes click type, and POSTs to the client's endpoints.

Supporting directories: `ansible/` (deployment playbooks/roles for server + clients), `script/` (cron-invoked shell wrappers, deploy scripts), `snapweb/` (a prebuilt custom Snapweb frontend, not built from source here — see `fe9aa68`).

## Commands

### server/

```
cd server
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # installs runtime + black + pytest
pytest                        # full suite (testpaths = tests/)
pytest tests/vcal/calendar/test_google_calendar.py       # one file
pytest tests/vcal/calendar/test_google_calendar.py::TestName::test_it  # one test
```

Requires `mpd`, `mpc`, `snapcast`, `ffmpeg` installed locally (see `server/README.md` for mac/linux setup, including MPD socket config). Manual (non-pytest) integration scripts live in `server/tests/manual/*.sh` and are run directly, not via pytest.

Entry points (defined in `server/pyproject.toml`, callable after `pip install -e .`):
- `cal-alarm-check` / `cal-alarm-stop` / `cal-alarm-test` / `play-test-file`
- `cal-announce` / `cal-announce-cached`
- `cal-data-refresh`

Run the HTTP admin server locally: `python index.py` (from `server/`, reads `config/uvicorn.yaml`).

### client/

```
cd client
python -m venv .venv && source .venv/bin/activate
pip install -e .
script/start.sh    # activates venv and runs index.py
```

No test suite currently exists for this project.

### bluetooth-button-listener/

```
cd bluetooth-button-listener
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest tests/test_listen.py
```

Can also be run directly with `--replay <captured.jsonl>` against `btb/listen.py` to debug BLE payload decoding without a live button (see the module docstring).

### Deployment

Deploys go through Ansible from a dev machine (requires `ansible` + `ts` from moreutils on macOS):
```
script/deploy/audio_host.sh       # deploys server
script/deploy/audio_clients.sh    # deploys room clients
script/deploy/bluetooth_button_listener.sh
```
`ansible/secrets.yml` (gitignored, must be created locally) needs `travnas_pass` and `pi_pass` and `travnas_ssh_public_key`.

## Architecture

### server/vcal — the core domain logic

- **`vcal/cal/google_calendar.py`** — fetches events from Google Calendar, caches them to `calendar.json`. `Event.notifications()` scans an event's description for `#alarm` / `#alarm<N>` / `#announce` / `#announce<N>` tags (offset in minutes), plus rule-based notifications from `NotificationSettings.notification_rules` (matched by substring + optional owner). Cached data round-trips through `load_data_from_file` / `save_data_to_file` using dataclasses, not pydantic.
- **`vcal/notifications/alarm.py`** — `NotificationFinder` buckets due events into a time window (called from cron every 5 min via `check_for_alarms.py`). `AlarmAudio`/`AnnouncementAudio` build the actual playable file: TTS per event (via `text_to_voice.py` / gTTS), mixed with alarm/background music (via `sound.py`, which shells out to ffmpeg), looped per `AlarmSettings`. `play_notifications()` orchestrates volume changes via Snapcast and hands off to MPD to actually play.
- **`vcal/morning_announcements/core.py`** — the daily summary read out each morning (`cal-announce`, cron-triggered). Builds sentences from today's events + optional weather forecast events (calendar events named "Min ..."/"Max ..." are treated specially as `WeatherForecast`) + rotating prelude/fact text (state tracked via `last_used` timestamps in `MorningAnnouncementsSettings`, persisted back to YAML).
- **`vcal/scene.py`** — `Scene` vs `NullScene` (a `SceneProtocol`). Before playing an alarm/announcement, pauses or dips Music Assistant players (via Home Assistant) in the relevant areas and restores them after; state is persisted to a file so `restore_after_alarm()` can run from a separate HTTP-triggered process with no shared memory.
- **`vcal/snapcast.py` / `vcal/snapserver.py`** — `SnapserverManager` wraps the Snapserver JSON-RPC API. Volumes are per-usecase (`tts`/`voice`/`alarm`) and per-room (`SnapclientConfig.area`), configured in `config/snapcast.yaml`.
- **`vcal/notifications/mpd.py`** — thin wrapper around `python-musicpd` for actually playing files, with fade-up/fade-out helpers.
- **`housie_talkie/`** — a separate feature (voice-message intercom / recorded announcements) sharing the same MPD/Snapcast playback plumbing as alarms; `core.py`'s `play_tts_announcement`/`play_voice_announcement` reuse `Scene` and `SnapserverManager` the same way `notifications/alarm.py` does.
- **`vcal/wake_up_alarm/`** — a standalone wake-up alarm (random file from `WAKE_UP_ALARMS_DIRECTORY`), independent of the calendar-driven alarm flow but sharing MPD/Snapcast.

### Settings (`vcal/settings.py`)

Every settings group is a `pydantic_settings.BaseSettings` subclass backed by a YAML file under `server/config/` (one file per concern: `main.yaml`, `mpd.yaml`, `snapcast.yaml`, `google_calendar.yaml`, `morning_announcements.yaml`, `home_assistant.yaml`, `housie_talkie.yaml`, `notifications.yaml`). `YAMLSettings` adds a `.save()` that writes the model back to its YAML file — used when settings carry mutable runtime state (e.g. "last used" timestamps for facts/preludes, not just static config). `AppSettings` aggregates all groups for the admin UI (`vcal/admin_ui.py`) to edit as one form.

### Entry points and process boundaries

`server/index.py` is the always-on FastAPI app (systemd service `calendar-alarms-http.service`) serving the admin UI, Google OAuth callback, log viewers, and HTTP endpoints like alarm-stop. `check_for_alarms.py` and `morning_announcements.py` are separate short-lived scripts invoked by cron (see `server/crontab.txt`) via the wrapper scripts in `script/` — they are *not* run inside the FastAPI process. This split matters: anything that needs to affect a currently-playing alarm from the HTTP server (e.g. stopping it, restoring Music Assistant state) has to work via shared files/state rather than in-memory objects, since it's a different process (see `Scene.restore_after_alarm` being `@staticmethod`).

### client/ (per-room audio control)

Single-file FastAPI app (`client/index.py`) exposing `/audio/toggle` and `/audio/stop`, triggered by the bluetooth button listener's HTTP POSTs. On trigger it: mutes ALSA immediately via `amixer_control.py` for a fast response, then asynchronously either mutes the local Snapclient (`snapserver.py`) or pauses/toggles the Music Assistant player via a Home Assistant webhook (`music_assistant.py`), depending on what's currently playing. Requests run in a background thread with a non-blocking lock (`_operation_lock`) so overlapping button presses return `409` instead of queuing.

### bluetooth-button-listener/

`btb/listen.py` uses `bleak` to scan for BLE advertisements from one specific Shelly BLU button (matched by MAC address), decodes the BTHome v2 TLV payload to extract click type and battery level, and POSTs to the corresponding endpoint from `SINGLE_CLICK_ENDPOINT` / `DOUBLE_CLICK_ENDPOINT` / `LONG_CLICK_ENDPOINT` env vars (these normally point at a `client/` instance's `/audio/*` routes). `parse_bthome`/`extract_button_event` are pure functions kept separate from the bleak callback specifically so they're unit-testable against raw captured payloads — the test file doubles as a payload-replay tool (`--replay captured.jsonl`) for debugging real-world button behavior.
