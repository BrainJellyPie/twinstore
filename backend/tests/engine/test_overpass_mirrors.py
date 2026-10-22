"""A busy Overpass server (502/504, which happens for minutes at a time) moves the download to another server."""

import io
import json
import urllib.error

import pytest

from store_emulator.engine.town import osm


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _busy(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "Bad Gateway", {}, None)  # type: ignore[arg-type]


def test_a_busy_server_hands_over_to_the_next(monkeypatch: pytest.MonkeyPatch):
    asked: list[str] = []

    def urlopen(request, timeout):
        asked.append(request.full_url)
        if "overpass-api.de" in request.full_url:
            raise _busy(request.full_url, 502)
        return _Answer(json.dumps({"elements": [{"type": "node", "id": 1}]}).encode())

    monkeypatch.setattr(osm.urllib.request, "urlopen", urlopen)
    data = osm.fetch_overpass(37.5, 127.0, 300)
    assert data["elements"] and len(asked) == 2 and "kumi" in asked[1]


def test_every_server_busy_says_so_and_a_refused_query_does_not_retry(monkeypatch: pytest.MonkeyPatch):
    asked: list[str] = []

    def busy(request, timeout):
        asked.append(request.full_url)
        raise _busy(request.full_url, 504)

    monkeypatch.setattr(osm.urllib.request, "urlopen", busy)
    monkeypatch.setattr(osm.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="busy or unreachable right now .*HTTP 504.*Try again"):
        osm.fetch_overpass(37.5, 127.0, 300)
    assert len(asked) == len(osm.OVERPASS_MIRRORS) * 2   # every server, twice

    asked.clear()

    def refused(request, timeout):
        asked.append(request.full_url)
        raise _busy(request.full_url, 400)

    monkeypatch.setattr(osm.urllib.request, "urlopen", refused)
    with pytest.raises(RuntimeError, match="HTTP Error 400"):
        osm.fetch_overpass(37.5, 127.0, 300)
    assert len(asked) == 1


def test_own_servers_come_first(monkeypatch: pytest.MonkeyPatch):
    asked: list[str] = []

    def urlopen(request, timeout):
        asked.append(request.full_url)
        return _Answer(b'{"elements": []}')

    monkeypatch.setenv("TWINSTORE_OVERPASS_URL", "https://overpass.example.org/api/interpreter")
    monkeypatch.setattr(osm.urllib.request, "urlopen", urlopen)
    osm.fetch_overpass(37.5, 127.0, 300)
    assert asked == ["https://overpass.example.org/api/interpreter"]
