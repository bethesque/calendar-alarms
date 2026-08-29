from subprocess import CompletedProcess

from fastapi import FastAPI
from fastapi.testclient import TestClient

import homeaudio.audio.logs_ui as logs_ui_module
from homeaudio.audio.logs_ui import JournalctlRoutes


def _client(**kwargs):
    app = FastAPI()
    routes = JournalctlRoutes(service_name="calendar-alarms", route="/calendar-alarms", **kwargs)
    app.include_router(routes.router, prefix="/journalctl")
    return TestClient(app)


def test_journalctl_routes_shows_journal_output(monkeypatch):
    captured_args = []

    def fake_run(args, **kwargs):
        captured_args.append(args)
        return CompletedProcess(args, returncode=0, stdout="log line one\nlog line two\n", stderr="")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    response = _client().get("/journalctl/calendar-alarms")

    assert response.status_code == 200
    assert "log line one" in response.text
    assert "log line two" in response.text
    assert '<a href="/" class="back">' in response.text
    assert "calendar-alarms" in response.text  # title

    args = captured_args[0]
    assert args[0] == "journalctl"
    assert "--user" in args
    assert "SYSLOG_IDENTIFIER=calendar-alarms" in args
    assert "-r" in args  # newest first
    assert "-n" in args and args[args.index("-n") + 1] == "50"  # default_lines
    assert "--grep" in args and args[args.index("--grep") + 1] == r"\| (INFO|WARNING|ERROR|CRITICAL) \|"  # defaults to INFO
    assert '<option value="INFO" selected>INFO</option>' in response.text


def test_journalctl_routes_filters_by_level_query_param(monkeypatch):
    captured_args = []

    def fake_run(args, **kwargs):
        captured_args.append(args)
        return CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    response = _client().get("/journalctl/calendar-alarms?level=WARNING")

    assert response.status_code == 200
    assert '<option value="WARNING" selected>WARNING</option>' in response.text

    args = captured_args[0]
    # Matches the " | WARNING | " field in log_config.py's format string, not
    # journalctl's own -p priority (which is uniformly "info" for stdout-captured
    # services regardless of the Python logging level - see the comment in
    # logs_ui.py for why -p can't be used here). Also includes every level more
    # severe than WARNING.
    assert "--grep" in args and args[args.index("--grep") + 1] == r"\| (WARNING|ERROR|CRITICAL) \|"


def test_journalctl_routes_level_filter_includes_more_severe_levels(monkeypatch):
    captured_args = []

    def fake_run(args, **kwargs):
        captured_args.append(args)
        return CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    expected_patterns = {
        "DEBUG": r"\| (DEBUG|INFO|WARNING|ERROR|CRITICAL) \|",
        "INFO": r"\| (INFO|WARNING|ERROR|CRITICAL) \|",
        "WARNING": r"\| (WARNING|ERROR|CRITICAL) \|",
        "ERROR": r"\| (ERROR|CRITICAL) \|",
        "CRITICAL": r"\| (CRITICAL) \|",
    }

    for level, expected_pattern in expected_patterns.items():
        _client().get(f"/journalctl/calendar-alarms?level={level}")

        args = captured_args[-1]
        assert args[args.index("--grep") + 1] == expected_pattern, level


def test_journalctl_routes_all_option_shows_every_level(monkeypatch):
    captured_args = []

    def fake_run(args, **kwargs):
        captured_args.append(args)
        return CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    # The "All" <option> has value="", so selecting it submits level= explicitly -
    # distinct from omitting the param entirely, which defaults to INFO.
    response = _client().get("/journalctl/calendar-alarms?level=")

    assert response.status_code == 200
    assert '<option value="" selected>All</option>' in response.text

    args = captured_args[0]
    assert "--grep" not in args


def test_journalctl_routes_ignores_invalid_level_value(monkeypatch):
    captured_args = []

    def fake_run(args, **kwargs):
        captured_args.append(args)
        return CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    response = _client().get("/journalctl/calendar-alarms?level=bogus")

    assert response.status_code == 200
    assert '<option value="" selected>All</option>' in response.text

    args = captured_args[0]
    assert "--grep" not in args


def test_journalctl_routes_uses_n_query_param_over_default(monkeypatch):
    captured_args = []

    def fake_run(args, **kwargs):
        captured_args.append(args)
        return CompletedProcess(args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    response = _client(default_lines=50).get("/journalctl/calendar-alarms?n=10")

    assert response.status_code == 200
    assert 'value="10"' in response.text

    args = captured_args[0]
    assert args[args.index("-n") + 1] == "10"


def test_journalctl_routes_shows_stderr_when_journalctl_fails(monkeypatch):
    def fake_run(args, **kwargs):
        return CompletedProcess(args, returncode=1, stdout="", stderr="no journal files were found")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    response = _client().get("/journalctl/calendar-alarms")

    assert response.status_code == 200
    assert "no journal files were found" in response.text


def test_journalctl_routes_handles_missing_journalctl_binary(monkeypatch):
    def fake_run(args, **kwargs):
        raise FileNotFoundError("journalctl")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    response = _client().get("/journalctl/calendar-alarms")

    assert response.status_code == 200
    assert "journalctl is not available on this host." in response.text


def test_journalctl_routes_escapes_log_content(monkeypatch):
    def fake_run(args, **kwargs):
        return CompletedProcess(args, returncode=0, stdout="<script>alert('x')</script>", stderr="")

    monkeypatch.setattr(logs_ui_module, "run", fake_run)

    response = _client().get("/journalctl/calendar-alarms")

    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
