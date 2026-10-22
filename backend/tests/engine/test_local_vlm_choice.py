"""The local model downloads only when the user asks for it; afterwards it comes back by itself until they stop it."""

import io
import os

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm
from store_emulator.application.hardware import HardwareProfile
from store_emulator.application.local_vlm import NOT_DOWNLOADED, LocalVLMManager


class _Net:
    """Every download the manager tries; each one answers with a few bytes."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def __call__(self, req):
        self.asked.append(req.full_url)
        return _Body(b"model")


class _Body(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}


def _manager(tmp_path, monkeypatch, net: _Net) -> tuple[LocalVLMManager, list[str]]:
    served: list[str] = []
    mgr = LocalVLMManager(tmp_path / "local_vlm", opener=net,
                          hardware=lambda: HardwareProfile(os="linux", arch="x64", cores=2, threads=2))
    monkeypatch.delenv("TWINSTORE_LOCAL_VLM", raising=False)
    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    monkeypatch.setattr(mgr, "_answers", lambda port: False)

    def runtime(hw, plan):       # a llama.cpp build already unpacked is used; any other would be downloaded
        build = mgr.home / "bin" / plan.backend
        if not (build / ".complete").is_file():
            mgr._check_download()  # pyright: ignore[reportPrivateUsage]
        return build / "llama-server"

    monkeypatch.setattr(mgr, "_runtime", runtime)
    monkeypatch.setattr(mgr, "_serve", lambda server, model, mmproj, plan: (
        served.append(model.name), mgr._set(state="ready", message="")))  # pyright: ignore[reportPrivateUsage]
    return mgr, served


def _settle(mgr: LocalVLMManager) -> None:
    if mgr._thread is not None:  # pyright: ignore[reportPrivateUsage]
        mgr._thread.join(timeout=10)  # pyright: ignore[reportPrivateUsage]


def _put_on_disk(mgr: LocalVLMManager) -> None:
    _, plan = mgr.plan()
    build = mgr.home / "bin" / plan.backend
    build.mkdir(parents=True)
    (build / ".complete").write_text("b1 build\n")
    (build / "llama-server").write_bytes(b"#!")
    models = mgr.home / "models" / plan.model.repo.replace("/", "__")
    models.mkdir(parents=True)
    for name in (plan.model.file, plan.model.mmproj):
        (models / name).write_bytes(b"gguf")


def test_a_start_nobody_asked_for_downloads_nothing(tmp_path, monkeypatch):
    net = _Net()
    mgr, served = _manager(tmp_path, monkeypatch, net)
    assert mgr.auto_start()
    _settle(mgr)
    assert net.asked == [] and served == []
    status = mgr.status()
    assert status.state == "off" and status.message == NOT_DOWNLOADED
    assert not mgr.on_disk(mgr.plan()[1])


def test_a_model_already_on_this_computer_starts_without_a_download(tmp_path, monkeypatch):
    net = _Net()
    mgr, served = _manager(tmp_path, monkeypatch, net)
    _put_on_disk(mgr)
    assert mgr.on_disk(mgr.plan()[1])
    mgr.auto_start()
    _settle(mgr)
    assert net.asked == [] and len(served) == 1 and mgr.status().state == "ready"


def test_the_users_start_downloads_and_is_remembered(tmp_path, monkeypatch):
    net = _Net()
    mgr, served = _manager(tmp_path, monkeypatch, net)
    mgr.choose(True)
    mgr.start()
    _settle(mgr)
    assert len(net.asked) == 2 and len(served) == 1        # the model and its image encoder

    again, _ = _manager(tmp_path, monkeypatch, _Net())    # the app opens again: an interrupted download goes on
    assert again.chosen() is True


def test_a_user_who_chose_it_gets_an_interrupted_download_finished(tmp_path, monkeypatch):
    net = _Net()
    mgr, served = _manager(tmp_path, monkeypatch, net)
    mgr.choose(True)
    assert mgr.auto_start()
    _settle(mgr)
    assert len(net.asked) == 2 and len(served) == 1


def test_after_the_user_stops_it_it_stays_off(tmp_path, monkeypatch):
    net = _Net()
    mgr, served = _manager(tmp_path, monkeypatch, net)
    _put_on_disk(mgr)
    mgr.choose(False)
    assert not mgr.auto_start()
    assert mgr._thread is None and served == []  # pyright: ignore[reportPrivateUsage]


def test_start_pressed_while_a_quiet_start_runs_goes_on_to_download(tmp_path, monkeypatch):
    net = _Net()
    mgr, served = _manager(tmp_path, monkeypatch, net)
    original = mgr.plan
    pressed = {"done": False}

    def plan():
        if not pressed["done"]:
            pressed["done"] = True
            mgr.start()              # the user's Start arrives while the quiet start is reading the hardware
        return original()

    monkeypatch.setattr(mgr, "plan", plan)
    mgr.auto_start()
    _settle(mgr)
    assert len(net.asked) == 2 and len(served) == 1 and mgr.status().state == "ready"


@pytest.mark.parametrize("content", ["", "{", "[]", '{"use": "yes"}'])
def test_an_unreadable_choice_counts_as_never_asked(tmp_path, monkeypatch, content):
    mgr, _ = _manager(tmp_path, monkeypatch, _Net())
    mgr.home.mkdir(parents=True)
    (mgr.home / "choice.json").write_text(content)
    assert mgr.chosen() is None


def test_opening_the_app_with_no_key_downloads_nothing(tmp_path, monkeypatch):
    from store_emulator.server import main

    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.endswith("_API_KEY"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "1")
    net = _Net()
    mgr, served = _manager(tmp_path, monkeypatch, net)
    monkeypatch.setattr(main, "local_vlm", lambda: mgr)
    monkeypatch.setattr(main, "cloud_providers_with_key", list)
    with TestClient(main.app):
        _settle(mgr)
    assert net.asked == [] and served == []


def test_the_settings_buttons_record_the_choice(tmp_path, monkeypatch):
    from store_emulator.server import main
    from store_emulator.server.routes import system

    mgr, _ = _manager(tmp_path, monkeypatch, _Net())
    monkeypatch.setattr(system, "manager", lambda: mgr)
    monkeypatch.setattr(local_vlm, "manager", lambda: mgr)
    client = TestClient(main.app)
    assert client.post("/api/system/local-model/start").status_code == 200
    _settle(mgr)
    assert mgr.chosen() is True
    assert client.post("/api/system/local-model/stop").status_code == 200
    assert mgr.chosen() is False
    setup = client.get("/api/system/models").json()
    assert setup["local"]["downloaded"] is True
