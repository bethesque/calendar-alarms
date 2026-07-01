from subprocess import run
from unittest import result
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from html import escape


class LogsRoutes:
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
                <h1>Service Status</h1>
                <pre>{output}</pre>
            </body>
            </html>
            """
        )