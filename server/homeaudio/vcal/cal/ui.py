from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse
from homeaudio.env import CALENDAR_DATA_DIRECTORY

TOKEN_PATH = f"{CALENDAR_DATA_DIRECTORY}/token.json"
PAGE_TITLE = "Upload Google API token.json"

class TokenRoutes:
    def __init__(self, back_path):
        self.router = APIRouter()
        self.back_path = back_path

        self.router.add_api_route(
            "/upload",
            self.upload_token_form,
            methods=["GET"]
        )

        self.router.add_api_route(
            "/upload",
            self.upload_token,
            methods=["POST"],
            name="upload_post"
        )

    async def upload_token_form(self, request: Request):
        action = request.url_for("upload_post")

        return HTMLResponse(
            f"""
            <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{PAGE_TITLE}</title>
                    <link rel="stylesheet" href="/static/styles.css">
                </head>
                <body>
                    <div class="header">
                        <a href="{self.back_path}" class="back">⬅️</a>
                        <h1>{PAGE_TITLE}</h1>
                    </div>
                    <div class="card">
                        <form action="{action}" method="post" enctype="multipart/form-data">
                            <input type="file" name="token" accept="application/json" required>
                            <button type="submit">Upload</button>
                        </form>
                    </div>
                </body>
            </html>
            """,
            status_code=200,
        )

    async def upload_token(self, token: UploadFile = File(...)):
        with open(TOKEN_PATH, "wb") as f:
            while chunk := await token.read(65536):
                f.write(chunk)

        return HTMLResponse(
            f"""
            <html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>{PAGE_TITLE}</title>
                    <link rel="stylesheet" href="/static/styles.css">
                </head>
                <body>
                    <div class="header">
                        <a href="{self.back_path}" class="back">⬅️</a>
                        <h1>{PAGE_TITLE}</h1>
                    </div>
                    <div class="card">
                        Google API token uploaded.
                    </div>
                </body>
            </html>
            """,
            status_code=200,
        )
