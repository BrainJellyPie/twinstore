"""A model obeying the grounding prompt must map back to the requested photo region."""

import asyncio
import base64
import io

import pytest
from PIL import Image

from store_emulator.engine.capture import detect
from store_emulator.engine.capture.frame import make_frame


@pytest.mark.parametrize("model,convention", [
    ("openai/qwen3-vl", "auto"), ("ollama/qwen3.5", "auto"), ("openai/Qwen-3-VL", "auto"),
    ("gemini/gemini-3.8-flash", "auto"), ("openai/qwen2.5-vl", "auto"),
    ("openai/local-model", "auto"), ("openai/qwen3-vl", "pixels"),
    ("gemini/gemini-3.8-flash", "norm1000"), ("openai/local-model", "norm1"),
    ("openai/local-model", "gemini"),
])
@pytest.mark.parametrize("size", [(800, 400), (400, 800)])
def test_prompt_and_decoder_use_one_coordinate_convention(monkeypatch, model, convention, size):
    prompts, decoded = [], []

    class ObedientModel:
        async def generate_structured_with_image_async(self, schema, system, prompt, url, **kwargs):
            prompts.append(prompt)
            with Image.open(io.BytesIO(base64.b64decode(url.partition(",")[2]))) as image:
                width, height = image.size
            # A fixed asymmetric region of the image, expressed in the units the prompt asks for.
            xy = [0.125, 0.25, 0.375, 0.75]
            if "Coordinates: [ymin, xmin, ymax, xmax]" in prompt:
                assert '"box_2d": [ymin, xmin, ymax, xmax]' in prompt
                box = [xy[i] * 1000 for i in [1, 0, 3, 2]]
            elif "normalised to 0-1000" in prompt:
                box = [v * 1000 for v in xy]
            elif "as fractions 0-1" in prompt:
                box = xy
            else:
                assert f"Coordinates: pixels of this {width}x{height} image" in prompt
                box = [xy[i] * (width if i % 2 == 0 else height) for i in range(4)]
            return schema.model_validate({"products": [{"box_2d": box, "label": "product"}]})

    def keep(frame, bands, boxes, **kwargs):
        decoded.extend(boxes)
        return boxes, bands

    monkeypatch.setattr(detect, "refine_detections", keep)
    with Image.new("RGB", size) as photo:
        frame = make_frame(photo)
        detector = detect.VLMGroundingDetector(ObedientModel(), model=model, convention=convention, max_side=384)
        boxes, _ = asyncio.run(detector.detect(frame, []))
    assert detector.calls == len(prompts) == len(boxes) == len(decoded) == 1
    width, height = frame.size
    assert (boxes[0].x1, boxes[0].y1, boxes[0].x2, boxes[0].y2) == pytest.approx(
        (width * 0.125, height * 0.25, width * 0.375, height * 0.75))
