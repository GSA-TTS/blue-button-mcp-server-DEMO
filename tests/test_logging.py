import logging

import httpx
import pytest

from src.blue_button.auth import BlueButtonTokenVerifier
from src.blue_button.utils import call_api

SENSITIVE_DATA = "Jane Veteran SSN 123-45-6789 DOB 1945-01-01"


class StubAsyncClient:
    def __init__(self, response: httpx.Response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def get(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_fhir_error_response_body_is_not_logged(monkeypatch, caplog):
    request = httpx.Request("GET", "https://sandbox.bluebutton.cms.gov/v2/fhir/Patient/1")
    response = httpx.Response(400, text=SENSITIVE_DATA, request=request)
    monkeypatch.setattr(
        "src.blue_button.utils.httpx.AsyncClient",
        lambda **kwargs: StubAsyncClient(response),
    )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(httpx.HTTPStatusError):
            await call_api("secret-token", "fhir/Patient/1")

    assert "failed with status 400" in caplog.text
    assert SENSITIVE_DATA not in caplog.text
    assert "secret-token" not in caplog.text
    assert "/fhir/Patient/1" not in caplog.text


@pytest.mark.asyncio
async def test_userinfo_error_response_body_is_not_logged(monkeypatch, caplog):
    request = httpx.Request("GET", "https://sandbox.bluebutton.cms.gov/v2/connect/userinfo")
    response = httpx.Response(401, text=SENSITIVE_DATA, request=request)
    monkeypatch.setattr(
        "src.blue_button.auth.httpx.AsyncClient",
        lambda **kwargs: StubAsyncClient(response),
    )
    verifier = BlueButtonTokenVerifier("https://sandbox.bluebutton.cms.gov/v2")

    with caplog.at_level(logging.DEBUG):
        await verifier.verify_token("secret-token")

    assert "userinfo returned 401" in caplog.text
    assert SENSITIVE_DATA not in caplog.text
    assert "secret-token" not in caplog.text
