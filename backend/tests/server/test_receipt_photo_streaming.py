"""Receipt uploads reach the reader one bounded photo at a time."""

import asyncio
import io

from fastapi import UploadFile
import pytest

from store_emulator.application import vision_inputs
from store_emulator.application.vision_inputs import ReceiptsResult
from store_emulator.server.routes import vision_inputs as routes


@pytest.mark.parametrize("sizes", [(10, 20, 30), (256, 257, 258), (1000000, 1000000, 1000000)])
def test_uploads_are_read_lazily_with_the_per_photo_limit(monkeypatch, sizes):
    monkeypatch.setattr(vision_inputs, "MAX_PHOTO_BYTES", 256)
    files = [io.BytesIO(b"x" * size) for size in sizes]
    uploads = [UploadFile(file=file, filename=f"r{i}.png") for i, file in enumerate(files)]
    consumed = []

    def read(pid, photos, **kwargs):
        assert all(file.tell() == 0 for file in files), "the whole batch was buffered before reading any receipt"
        for i, data in enumerate(photos):
            assert len(data) == min(sizes[i], 257)
            assert all(file.tell() == 0 for file in files[i + 1:])
            consumed.append(len(data))
        return ReceiptsResult(receipts=[], matched_lines=0, unmatched_lines=0, csv="", currency="USD")

    monkeypatch.setattr(vision_inputs, "read_receipts", read)
    asyncio.run(routes.receipts("project", uploads, setup_id="", run_id="", model="offline"))
    assert consumed == [min(size, 257) for size in sizes]
