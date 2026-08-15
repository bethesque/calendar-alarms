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