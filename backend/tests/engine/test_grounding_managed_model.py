"""A managed model's API alias must not hide its known grounding coordinates."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.application import capture, local_vlm, providers
from store_emulator.application.hardware import HardwareProfile, MODEL_BY_KEY, recommend
from store_emulator.application.local_vlm import LocalVLMStatus
from store_emulator.domain.capture import CaptureOptions
from store_emulator.domain.config import SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture import detect
from store_emulator.engine.capture.frame import make_frame


BASE = "http://127.0.0.1:8081/v1"


def managed_client(monkeypatch, model, mode="json_schema"):
    plan = recommend(HardwareProfile(os="linux", arch="x64", cores=4, ram_gb=8, ram_free_gb=4))
    status = LocalVLMStatus(state="ready", managed=True, api_base=BASE, slots=1,
                            plan=plan.model_copy(update={"model": MODEL_BY_KEY[model]}))
    monkeypatch.setattr(local_vlm, "manager", lambda: SimpleNamespace(status=lambda: status))
    monkeypatch.setattr(providers, "load_settings", lambda: {})
    config = capture.capture_llm_config(SimulationConfig(), "llamacpp:local")
    assert config is not None and config.cache_namespace.startswith("managed-local:")
    assert config.model == "openai/local-model" and config.api_base == BASE
    return llm_client.LiteLLMClient(config.model_copy(update={"structured_output": mode})), status


@pytest.mark.parametrize("model", ["qwen3.5-0.8b", "qwen3.5-2b", "qwen3.5-4b", "qwen3.5-9b", "lfm2.5-vl-450m"])
@pytest.mark.parametrize("size", [(800, 400), (400, 800)])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_managed_alias_uses_loaded_family_without_changing_request_model(monkeypatch, tmp_path, model, size, mode):
    monkeypatch.chdir(tmp_path)
    original, requests = llm_client.litellm.acompletion, []
    monkeypatch.setattr(detect, "refine_detections", lambda frame, bands, boxes, **kwargs: (boxes, bands))
    is_qwen = model.startswith("qwen")
    # Every normalised coordinate fits within BOTH resized image dimensions:
    # the generic overflow heuristic cannot distinguish these from pixels.
    coordinates = [125, 100, 375, 300]

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"products": [{"box_2d": coordinates}]})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url=BASE, http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client, _ = managed_client(monkeypatch, model, mode)
            detector = capture.choose_detector(CaptureOptions(detector="vlm", model="llamacpp:local"), client)
            with Image.new("RGB", size) as photo:
                frame = make_frame(photo)
                boxes, bands = await detector.detect(frame, [])
                assert len(boxes) == 1 and bands == []
                expected = (size[0] * .125, size[1] * .1, size[0] * .375, size[1] * .3) if is_qwen else tuple(v / .96 for v in coordinates)
                assert (boxes[0].x1, boxes[0].y1, boxes[0].x2, boxes[0].y2) == pytest.approx(expected)
                assert await detector.detect(frame, []) == (boxes, bands)
            assert len(requests) == 1 and requests[0]["model"] == "local-model"
            prompt = json.dumps(requests[0]["messages"])
            assert ("normalised to 0-1000" in prompt) == is_qwen
            assert ("Coordinates: pixels" in prompt) == (not is_qwen)
            assert client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("condition", ["unmanaged", "stopped", "no_plan", "no_endpoint", "other_port", "host_alias", "no_identity", "trailing_slash"])
def test_only_matching_ready_managed_metadata_can_supply_the_family(monkeypatch, tmp_path, condition):
    monkeypatch.chdir(tmp_path)
    client, status = managed_client(monkeypatch, "qwen3.5-2b")
    if condition == "unmanaged":
        status.managed = False
    elif condition == "stopped":
        status.state = "off"
    elif condition == "no_plan":
        status.plan = None
    elif condition == "no_endpoint":
        status.api_base = None
    elif condition == "other_port":
        status.api_base = "http://127.0.0.1:9090/v1"
    elif condition == "host_alias":
        status.api_base = "http://localhost:8081/v1"
    elif condition == "no_identity":
        client.cache_namespace = ""
    else:
        status.api_base = BASE + "/"
    detector = capture.choose_detector(CaptureOptions(detector="vlm", model="llamacpp:local"), client)
    assert detector.convention == ("norm1000" if condition == "trailing_slash" else "auto")
    assert detector.model == ("qwen3.5-2b" if condition == "trailing_slash" else "openai/local-model")
    assert client.model == "openai/local-model"
