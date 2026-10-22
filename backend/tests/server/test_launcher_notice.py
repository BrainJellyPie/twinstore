"""The console notice with no API key does not promise a model download nobody asked for."""

import pytest

from store_emulator import launcher
from store_emulator.application import providers


def test_no_key_notice_points_to_settings_without_an_unasked_download(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(providers, "cloud_providers_with_key", list)
    notice = launcher.no_key_notice()
    assert notice is not None
    assert "Settings → Model providers" in notice and "nothing is downloaded until you do" in notice
    assert "downloaded on first use" not in notice


def test_no_notice_with_a_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(providers, "cloud_providers_with_key", lambda: ["OpenAI"])
    assert launcher.no_key_notice() is None
