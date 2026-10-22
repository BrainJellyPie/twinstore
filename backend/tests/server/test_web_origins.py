"""Only TwinStore's own pages (on this computer) may use the API: any other site the user visits must not read the
stores, change the model settings or quit the app."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from store_emulator.server.main import app, guard_origins

EVIL = "https://evil.example"


def _client(monkeypatch: pytest.MonkeyPatch, allowed: str = "") -> TestClient:
    monkeypatch.setenv("TWINSTORE_ALLOWED_ORIGINS", allowed)
    target = FastAPI()

    @target.get("/api/thing")
    async def read() -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]  (the decorator registers it)
        return {"ok": True}

    @target.post("/api/thing")
    async def change() -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        return {"changed": True}

    guard_origins(target)
    return TestClient(target)


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:8000", "http://[::1]:8000",
                                    "http://localhost"])
def test_pages_on_this_computer_may_read_and_change(monkeypatch: pytest.MonkeyPatch, origin: str):
    client = _client(monkeypatch)
    read = client.get("/api/thing", headers={"Origin": origin})
    assert read.status_code == 200 and read.headers["access-control-allow-origin"] == origin
    preflight = client.options("/api/thing", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                      "Access-Control-Request-Headers": "content-type"})
    assert preflight.status_code == 200
    # The development UI on 127.0.0.1 calling localhost is cross-site to the browser, and still this computer's.
    changed = client.post("/api/thing", headers={"Origin": origin, "Sec-Fetch-Site": "cross-site"})
    assert changed.status_code == 200 and changed.json() == {"changed": True}


def test_other_sites_cannot_read_or_change(monkeypatch: pytest.MonkeyPatch):
    client = _client(monkeypatch)
    read = client.get("/api/thing", headers={"Origin": EVIL})
    assert "access-control-allow-origin" not in read.headers  # the browser keeps the answer from the page
    preflight = client.options("/api/thing", headers={"Origin": EVIL, "Access-Control-Request-Method": "PUT"})
    assert "access-control-allow-origin" not in preflight.headers
    for headers in ({"Origin": EVIL}, {"Origin": "null"}, {"Origin": "http://localhost.evil.example"},
                    {"Origin": "http://127.0.0.1.evil.example:8000"}, {"Sec-Fetch-Site": "cross-site"}):
        refused = client.post("/api/thing", headers=headers)  # a body-less POST is sent without asking first
        assert refused.status_code == 403, headers


def test_programs_and_the_apps_own_pages_still_change(monkeypatch: pytest.MonkeyPatch):
    client = _client(monkeypatch)
    for headers in ({}, {"Sec-Fetch-Site": "same-origin"}, {"Sec-Fetch-Site": "none"}):
        assert client.post("/api/thing", headers=headers).status_code == 200, headers


def test_origins_the_user_lists_are_allowed(monkeypatch: pytest.MonkeyPatch):
    client = _client(monkeypatch, "http://192.168.0.5:5173/, https://lab.example ")
    for origin in ("http://192.168.0.5:5173", "https://lab.example"):
        read = client.get("/api/thing", headers={"Origin": origin})
        assert read.headers["access-control-allow-origin"] == origin
        assert client.post("/api/thing", headers={"Origin": origin, "Sec-Fetch-Site": "cross-site"}).status_code == 200
    assert client.post("/api/thing", headers={"Origin": EVIL}).status_code == 403


def test_the_server_is_guarded():
    client = TestClient(app)  # no lifespan: nothing starts
    assert client.post("/api/health", headers={"Origin": EVIL}).status_code == 403
    assert client.post("/api/health", headers={"Origin": "http://localhost:5173"}).status_code == 405
    read = client.get("/api/health", headers={"Origin": EVIL})
    assert read.status_code == 200 and "access-control-allow-origin" not in read.headers


def test_the_apps_own_page_opened_by_ip_from_another_device_still_changes(monkeypatch: pytest.MonkeyPatch):
    client = _client(monkeypatch)
    for address in ("192.168.0.7:8000", "[fe80::1]:8000"):
        same = client.post("/api/thing", headers={"Origin": f"http://{address}", "Host": address})
        assert same.status_code == 200, address
    # A name pointed at this computer by another site is not the app's own page.
    rebound = client.post("/api/thing", headers={"Origin": "http://evil.example:8000", "Host": "evil.example:8000"})
    assert rebound.status_code == 403
    other = client.post("/api/thing", headers={"Origin": "http://192.168.0.9:8000", "Host": "192.168.0.7:8000"})
    assert other.status_code == 403
