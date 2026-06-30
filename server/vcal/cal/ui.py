import google_auth_oauthlib.flow
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse
from vcal.settings import GoogleCalendarSettings

class GoogleCalendarAuthRoutes:
    def __init__(self):
        self.settings = GoogleCalendarSettings()
        self.router = APIRouter()

        self.router.add_api_route(
            "/login",
            self.login,
            methods=["GET"],
        )

        self.router.add_api_route(
            "/auth",
            self.auth,
            methods=["GET"],
        )

    async def login(self):
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            "client_secret.json",
            scopes=[self.settings.scope],
            state="alwaysTheSame",
        )

        flow.redirect_uri = f"{self.settings.redirect_server}/auth"

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state="alwaysTheSame",
            login_hint=self.settings.login_hint,
            prompt="consent",
        )

        return RedirectResponse(url=authorization_url)

    async def auth(
        self,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ):
        if state != "alwaysTheSame":
            return HTMLResponse(f"Something is up with your state: {state}")

        if error:
            return HTMLResponse(f"Something went wrong! {error}")

        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            "client_secret.json",
            scopes=[self.settings.scope],
            state=state,
        )

        flow.redirect_uri = f"{self.settings.redirect_server}/auth"
        flow.fetch_token(code=code)

        with open("token.json", "w") as f:
            f.write(flow.credentials.to_json())

        return HTMLResponse(
            "The Calendar Alarms credentials have been updated."
        )
