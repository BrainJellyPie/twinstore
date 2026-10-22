"""Requests to servers on this computer bypass a proxy taken from the system settings."""

import os
import urllib.request

import pytest

from store_emulator import launcher


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch):
    for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)


def test_the_system_proxy_moves_into_the_environment_with_loopback_exempt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"http": "http://proxy.corp:8080", "https": "http://proxy.corp:8080"})
    launcher.keep_local_requests_direct()
    assert os.environ["https_proxy"] == os.environ["http_proxy"] == "http://proxy.corp:8080"
    assert os.environ["no_proxy"] == os.environ["NO_PROXY"] == "127.0.0.1,localhost,::1"
    assert urllib.request.proxy_bypass_environment("127.0.0.1")


def test_a_proxy_and_bypass_list_the_user_set_are_kept(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://mine:3128")
    monkeypatch.setenv("NO_PROXY", "intranet.local,localhost")
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"https": "http://other:8080"})
    launcher.keep_local_requests_direct()
    assert "https_proxy" not in os.environ or os.environ["https_proxy"] == "http://mine:3128"
    assert os.environ["NO_PROXY"] == "intranet.local,localhost,127.0.0.1,::1"


def test_no_proxy_anywhere_changes_only_the_bypass_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {})
    launcher.keep_local_requests_direct()
    assert "http_proxy" not in os.environ and "https_proxy" not in os.environ
    assert os.environ["no_proxy"] == "127.0.0.1,localhost,::1"
