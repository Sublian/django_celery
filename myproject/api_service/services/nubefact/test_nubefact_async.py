import asyncio
import pytest
from types import SimpleNamespace

import httpx

from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync


@pytest.mark.asyncio
async def test_init_and_token_formatting(monkeypatch):
    mock_service = SimpleNamespace(base_url="https://api.nubefact.test", auth_token="abc123")

    # Patch BaseAPIService.__init__ behavior by creating instance and overriding attributes
    svc = object.__new__(NubefactServiceAsync)
    svc.service = mock_service
    svc.token = svc.auth_token
    svc._client = None
    svc.timeout = NubefactServiceAsync.DEFAULT_TIMEOUT
    svc._validate_and_format_token = lambda t: (t if t.startswith("Bearer ") else f"Bearer {t}")

    headers = svc._build_headers()
    assert headers["Authorization"].startswith("Bearer ") or headers["Authorization"] == "Bearer abc123"


@pytest.mark.asyncio
async def test_send_request_success(monkeypatch):
    mock_endpoint = SimpleNamespace(path="/v1/generar", name="generar_comprobante")

    svc = object.__new__(NubefactServiceAsync)
    svc.service = SimpleNamespace(base_url="https://api.nubefact.test", auth_token="abc123")
    svc._client = None
    svc.timeout = NubefactServiceAsync.DEFAULT_TIMEOUT
    svc._validate_and_format_token = lambda t: (t if t.startswith("Bearer ") else f"Bearer {t}")
    svc._initialized = True
    svc._executor = None  # Not used in this test

    # Patch _get_endpoint_sync to return our mock endpoint
    monkeypatch.setattr(svc, "_get_endpoint_sync", lambda name: mock_endpoint)
    monkeypatch.setattr(svc, "_check_rate_limit_sync", lambda name: (True, 0.0))

    class DummyResp:
        status_code = 200

        def json(self):
            return {"success": True, "id": "abc"}

    async def mock_post(url, json=None, **kwargs):
        return DummyResp()

    # Ensure client is created and monkeypatch its post
    await svc._ensure_client()
    monkeypatch.setattr(svc._client, "post", mock_post)

    res = await svc.send_request("generar_comprobante", {"numero": "1"})
    assert res["success"] is True


@pytest.mark.asyncio
async def test_send_request_http_error(monkeypatch):
    mock_endpoint = SimpleNamespace(path="/v1/generar", name="generar_comprobante")

    svc = object.__new__(NubefactServiceAsync)
    svc.service = SimpleNamespace(base_url="https://api.nubefact.test", auth_token="abc123")
    svc._client = None
    svc.timeout = NubefactServiceAsync.DEFAULT_TIMEOUT
    svc._validate_and_format_token = lambda t: (t if t.startswith("Bearer ") else f"Bearer {t}")
    svc._initialized = True
    svc._executor = None  # Not used in this test
    monkeypatch.setattr(svc, "_get_endpoint_sync", lambda name: mock_endpoint)
    monkeypatch.setattr(svc, "_check_rate_limit_sync", lambda name: (True, 0.0))

    async def raise_request_error(*args, **kwargs):
        raise httpx.RequestError("network down")

    await svc._ensure_client()
    monkeypatch.setattr(svc._client, "post", raise_request_error)

    with pytest.raises(Exception):
        await svc.send_request("generar_comprobante", {"numero": "1"})
