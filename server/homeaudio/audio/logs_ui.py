from subprocess import run
from unittest import result
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from html import escape

from collections import deque
from html import escape
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

class JournalctlRoutes:
    # These services log via a plain StreamHandler to stdout (see log_config.py's
    # "%(levelname)s" format), and systemd's journal capture tags every stdout line
    # with the same syslog priority regardless of that - so journalctl's -p (which
    # filters on that priority metadata) can't distinguish them. Match the level
    # name as it actually appears in the formatted message text instead.
    LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(
        self,
        service_name: str,
        route: str,
        default_lines: int = 50,
    ) -> None:
        self.service_name = service_name
        self.default_lines = default_lines

        self.router = APIRouter()
        self.router.add_api_route(
            route,
            self.get_log,
            methods=["GET"],
            response_class=HTMLResponse,
        )

    async def get_log(
        self,
        n: int = Query(default=None, ge=1, le=1000),
        level: str | None = Query(default=None),
    ) -> HTMLResponse:
        line_count = n or self.default_lines

        if level is None:
            level = "INFO"  # default on first load; submitting "All" sends level="" explicitly
        level = level if level in self.LOG_LEVELS else None

        try:
            args = [
                "journalctl",
                "--user",
                f"SYSLOG_IDENTIFIER={self.service_name}",
                "-n", str(line_count),
                "-r",  # newest first
                "--no-pager",
            ]
            if level:
                # Matches the " | LEVEL | " field written by log_config.py's format string.
                # LOG_LEVELS is in increasing severity order, so this also matches every
                # level more severe than the selected one (e.g. INFO also shows WARNING/ERROR/CRITICAL).
                levels_at_or_above = self.LOG_LEVELS[self.LOG_LEVELS.index(level):]
                pattern = "|".join(levels_at_or_above)
                args += ["--grep", rf"\| ({pattern}) \|", "--case-sensitive=true"]

            result = run(args, capture_output=True, text=True)

            content = escape(result.stdout) if result.returncode == 0 else f"Error reading journal: {escape(result.stderr)}"

        except FileNotFoundError:
            content = "journalctl is not available on this host."
        except Exception as exc:
            content = f"Error reading journal: {escape(str(exc))}"

        level_options = "\n".join(
            f'<option value="{lvl}"{" selected" if lvl == level else ""}>{lvl}</option>'
            for lvl in self.LOG_LEVELS
        )

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Log Viewer</title>
                <link rel="stylesheet" href="/static/styles.css">
            </head>
            <body>
                <div class="header">
                    <a href="/" class="back">⬅️</a>
                    <h1>{escape(self.service_name)}</h1>
                </div>

                <form method="get">
                    <label for="n">Lines:</label>
                    <input
                        id="n"
                        name="n"
                        type="number"
                        min="1"
                        max="1000"
                        value="{line_count}"
                    >

                    <label for="level">Level:</label>
                    <select id="level" name="level">
                        <option value=""{" selected" if not level else ""}>All</option>
                        {level_options}
                    </select>

                    <button type="submit">Refresh</button>
                </form>

                <pre>{content}</pre>
            </body>
            </html>
            """
        )




class LogRoutes:
    def __init__(
        self,
        file_path: str | Path,
        route: str,
        default_lines: int = 50,
    ) -> None:
        self.file_path = Path(file_path)
        self.default_lines = default_lines

        self.router = APIRouter()
        self.router.add_api_route(
            route,
            self.get_log,
            methods=["GET"],
            response_class=HTMLResponse,
        )

    async def get_log(
        self,
        n: int = Query(default=None, ge=1, le=1000),
    ) -> HTMLResponse:
        line_count = n or self.default_lines

        try:
            with self.file_path.open("r", encoding="utf-8", errors="replace") as f:
                lines = deque(f, maxlen=line_count)

            # newest first
            content = "".join(
                escape(line)
                for line in reversed(lines)
            )

        except FileNotFoundError:
            content = f"File not found: {escape(str(self.file_path))}"
        except Exception as exc:
            content = f"Error reading file: {escape(str(exc))}"

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Log Viewer</title>
                <link rel="stylesheet" href="/static/styles.css">
            </head>
            <body>
                <h1>{escape(self.file_path.name)}</h1>

                <form method="get">
                    <label for="n">Lines:</label>
                    <input
                        id="n"
                        name="n"
                        type="number"
                        min="1"
                        max="1000"
                        value="{line_count}"
                    >
                    <button type="submit">Refresh</button>
                </form>

                <pre>{content}</pre>
            </body>
            </html>
            """
        )

class CalendarAlarmsStatusRoutes:
    SERVICE_NAME = "calendar-alarms-http.service"

    def __init__(self) -> None:
        self.router = APIRouter()
        self.router.add_api_route(
            "",
            self.get_status,
            methods=["GET"],
            response_class=HTMLResponse,
        )

    async def get_status(self) -> HTMLResponse:
        result = run(
            [
                "systemctl",
                "--user",
                "status",
                self.SERVICE_NAME,
            ],
            capture_output=True,
            text=True,
        )

        output = escape(result.stdout or result.stderr)

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Service Status</title>
                <link rel="stylesheet" href="/static/styles.css">
            </head>
            <body>
                <h1>{self.SERVICE_NAME}</h1>
                <pre>{output}</pre>
            </body>
            </html>
            """
        )