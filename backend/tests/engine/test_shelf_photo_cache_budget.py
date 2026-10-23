"""Shelf photo caching is bounded by retained memory as well as entry count."""

import io
import json
import weakref
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from PIL import Image

from store_emulator.engine.perception import shelf_photo


@pytest.fixture(autouse=True)
def empty_cache():
    shelf_photo.load_shelf_photo.cache_clear()
    yield
    shelf_photo.load_shelf_photo.cache_clear()


def jpeg(size, color="red"):
    stream = io.BytesIO()
    with Image.new("RGB", size, color) as picture:
        picture.save(stream, "JPEG")
    return stream.getvalue()


def write(folder, index, data, boxes=None):
    key = f"{index:064x}"
    (folder / f"{key}.jpg").write_bytes(data)
    (folder / f"{key}.json").write_text(json.dumps({"boxes": boxes or {"N:1:0:0": [[1, 2, 20, 30]]}}))
    return key


@pytest.mark.parametrize("side", [64, 512, 2048])
def test_large_photos_are_evicted_without_closing_live_callers(tmp_path, monkeypatch, side):
    monkeypatch.setattr(shelf_photo, "_PHOTO_CACHE_BYTES", side * side * 4 * 3 + 16_384, raising=False)
    data = jpeg((side, side))
    first = shelf_photo.load_shelf_photo(str(tmp_path), write(tmp_path, 0, data))
    assert first is not None
    retained = weakref.ref(first.image)
    for index in range(1, 6):
        photo = shelf_photo.load_shelf_photo(str(tmp_path), write(tmp_path, index, data))
        assert photo is not None and photo.image.size == (side, side)
    # Eviction cannot close a photo the renderer is still using.
    assert first.image.getpixel((0, 0))[0] > 240
    del first
    assert retained() is None


def test_small_photos_still_share_the_available_budget(tmp_path):
    data = jpeg((64, 64))
    first = shelf_photo.load_shelf_photo(str(tmp_path), write(tmp_path, 0, data))
    assert first is not None
    for index in range(1, 200):
        assert shelf_photo.load_shelf_photo(str(tmp_path), write(tmp_path, index, data)) is not None
    assert shelf_photo.load_shelf_photo(str(tmp_path), f"{0:064x}") is first


def test_hit_refreshes_eviction_order(tmp_path, monkeypatch):
    monkeypatch.setattr(shelf_photo, "_PHOTO_CACHE_BYTES", 512 * 512 * 4 * 2 + 16_384, raising=False)
    data = jpeg((512, 512))
    keys = [write(tmp_path, index, data) for index in range(3)]
    first = shelf_photo.load_shelf_photo(str(tmp_path), keys[0])
    second = shelf_photo.load_shelf_photo(str(tmp_path), keys[1])
    assert first is not None and second is not None
    old = weakref.ref(second.image)
    del second
    assert shelf_photo.load_shelf_photo(str(tmp_path), keys[0]) is first
    assert shelf_photo.load_shelf_photo(str(tmp_path), keys[2]) is not None
    assert old() is None


def test_box_metadata_also_consumes_the_cache_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(shelf_photo, "_PHOTO_CACHE_BYTES", 2 * 1024 * 1024, raising=False)
    data = jpeg((64, 64))
    boxes = {f"N:1:{index}:0": [[1, 2, 30, 50]] * 24 for index in range(400)}
    first = shelf_photo.load_shelf_photo(str(tmp_path), write(tmp_path, 0, data, boxes))
    assert first is not None
    retained = weakref.ref(first.image)
    del first
    for index in range(1, 4):
        assert shelf_photo.load_shelf_photo(str(tmp_path), write(tmp_path, index, data, boxes)) is not None
    assert retained() is None


def test_missing_photo_entries_are_still_bounded(tmp_path):
    for index in range(300):
        assert shelf_photo.load_shelf_photo(str(tmp_path), f"{index:064x}") is None
    key = write(tmp_path, 0, jpeg((64, 64)))
    assert shelf_photo.load_shelf_photo(str(tmp_path), key) is not None


def test_upload_during_decode_does_not_reinsert_an_invalidated_photo(tmp_path, monkeypatch):
    key = write(tmp_path, 0, jpeg((64, 64)))
    ready, release = Event(), Event()
    original = Image.Image.convert
    paused = False

    def convert(picture, *args, **kwargs):
        nonlocal paused
        result = original(picture, *args, **kwargs)
        if str(getattr(picture, "filename", "")) == str(tmp_path / f"{key}.jpg") and not paused:
            paused = True
            ready.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(Image.Image, "convert", convert)
    with ThreadPoolExecutor(max_workers=1) as pool:
        loading = pool.submit(shelf_photo.load_shelf_photo, str(tmp_path), key)
        try:
            assert ready.wait(5)
            shelf_photo.save_shelf_photo(tmp_path, key, jpeg((64, 64), "blue"), {})
        finally:
            release.set()
        assert loading.result(timeout=5) is not None
    current = shelf_photo.load_shelf_photo(str(tmp_path), key)
    assert current is not None and current.image.getpixel((0, 0))[2] > 240
