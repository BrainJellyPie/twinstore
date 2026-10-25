"""GIF export keeps only bounded full-color working frames for long visits."""

import io
import weakref

import pytest
from PIL import Image, PngImagePlugin

from store_emulator.engine.online.render import animate


@pytest.mark.parametrize("size", [(1024, 1200), (390, 900)])
@pytest.mark.parametrize("count", [1, 8])
def test_export_releases_full_size_rgb_screenshots_as_it_goes(monkeypatch, size, count):
    frames = []
    for index in range(count):
        with Image.new("RGB", (size[0], size[1] + index * 10), (200, index * 20, 230)) as page:
            png = io.BytesIO()
            page.save(png, format="PNG")
        frames.append((png.getvalue(), f"Step {index + 1}", "Looking at the products."))
    references = []
    peak = 0
    original = Image.Image.convert

    def tracked(self, *args, **kwargs):
        nonlocal peak
        converted = original(self, *args, **kwargs)
        if isinstance(self, PngImagePlugin.PngImageFile) and converted.mode == "RGB":
            references.append(weakref.ref(converted))
            peak = max(peak, sum(ref() is not None for ref in references))
        return converted

    monkeypatch.setattr(Image.Image, "convert", tracked)
    result = animate(frames)
    assert len(references) == count and peak <= 2
    assert not any(ref() is not None for ref in references)
    with Image.open(io.BytesIO(result)) as gif:
        width = min(640, size[0])
        assert gif.size == (width, round((size[1] + (count - 1) * 10) * width / size[0]) + 58)
        assert gif.n_frames == count and gif.info["loop"] == 0
        for index in range(count):
            gif.seek(index)
            assert gif.info["duration"] == (4800 if index == count - 1 else 1600)
            pixel = gif.convert("RGB").getpixel((0, 0))
            assert all(abs(actual - expected) <= 3 for actual, expected in zip(pixel, (200, index * 20, 230)))
