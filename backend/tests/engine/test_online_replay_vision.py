"""Replay must retain the eyesight transform actually presented to a vision policy."""

import asyncio
import base64
import io
import random

import pytest
from PIL import Image, ImageChops, ImageDraw

from store_emulator.application import online
from store_emulator.engine.online.policies import Choice, Memory, StepView
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers
from tests.engine.test_online_arrivals import _site


@pytest.mark.parametrize("vision", ["typical", "low_vision", "color_blind", "aging_eyes"])
@pytest.mark.parametrize("device,large,terminal", [
    ("desktop", False, False), ("mobile", False, False), ("desktop", True, False),
    ("mobile", True, False), ("desktop", False, True),
])
def test_replay_preserves_the_models_eyesight_and_selected_control(monkeypatch, vision, device, large, terminal):
    site = _site()
    site = site.model_copy(update={"options": site.options.model_copy(update={"large_text": large})})
    shopper = sample_shoppers(site, 1, seed=4, missions={"browse": 1.0}, mobile_share=0)[0].model_copy(update={
        "vision": vision, "device": device,
    })
    sent: list[str] = []

    class Capture:
        async def choose(self, site, shopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
            sent.append(view.image_url)
            return Choice(view.page.leave, source="model")

    session = asyncio.run(run_session(site, shopper, Capture(), seed=4, max_steps=1, render=True, image_width=1600))
    step = session.steps[0]
    if terminal:
        step.choice = None
    view = online.SessionView(variant=0, site_id=site.id, site_name=site.name, shopper=shopper, session=session)
    monkeypatch.setattr(online, "get_session", lambda *_: view)
    monkeypatch.setattr(online, "_snapshot", lambda *_: ([site], [shopper]))
    monkeypatch.setattr(online, "_picture", lambda *_: lambda _: None)
    replay = online.step_screenshot("p", "r", 0, shopper.id, 0)
    with Image.open(io.BytesIO(base64.b64decode(sent[0].split(",", 1)[1]))) as source:
        expected = source.convert("RGB")
    with Image.open(io.BytesIO(replay)) as source:
        actual = source.convert("RGB")
    assert actual.size == expected.size
    if step.choice is not None:
        assert step.choice.box is not None
        left, top, right, bottom = step.choice.box
        assert actual.getpixel((left - 3, (top + bottom) // 2)) == (244, 63, 94)
        mask = (left - 4, top - 4, right + 4, bottom + 4)
        ImageDraw.Draw(actual).rectangle(mask, fill="black")
        ImageDraw.Draw(expected).rectangle(mask, fill="black")
    assert ImageChops.difference(actual, expected).getbbox() is None
