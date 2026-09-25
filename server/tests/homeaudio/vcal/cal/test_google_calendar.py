from homeaudio.vcal.cal.google_calendar import load_google_creds


def test_load_google_creds_returns_none_when_no_token_info():
    assert load_google_creds(None) is None


def test_load_google_creds_loads_credentials_from_token_info():
    token_info = {
        "token": "access-token",
        "refresh_token": "refresh-token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "expiry": "2099-01-01T00:00:00Z",
    }

    creds = load_google_creds(token_info)

    assert creds.token == "access-token"
    assert creds.refresh_token == "refresh-token"
