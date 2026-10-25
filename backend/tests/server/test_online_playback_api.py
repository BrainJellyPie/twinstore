"""An animated playback of a visit: where each click landed, and the page without the drawn highlight."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from tests.server.test_online_rival_api import PID, _site, _wait, client  # noqa: F401  (fixture)


def test_each_step_gives_its_screen_and_the_clicked_box(client: TestClient) -> None:
    site = _site(client, "pet_store")
    runs = f"/api/projects/{PID}/online/runs"
    status = client.post(runs, json={"site_ids": [site["id"]], "shoppers": 4, "seed": 6, "max_steps": 14,
                                      "mobile_share": 0.5}).json()
    assert _wait(client, status["run_id"])["status"]["status"] == "completed"
    base = f"{runs}/{status['run_id']}/sessions/0"
    for shopper in ("os0001", "os0002", "os0003", "os0004"):
        steps = client.get(f"{base}/{shopper}").json()["session"]["steps"]
        frames = client.get(f"{base}/{shopper}/playback").json()
        assert [f["step"] for f in frames] == [s["index"] for s in steps]
        for frame, step in zip(frames, steps, strict=True):
            if step["choice"] is None:
                assert frame["box"] is None
                continue
            left, top, right, bottom = frame["box"]
            assert 0 <= left < right <= frame["width"] and 0 <= top < bottom <= frame["height"]
        first = next(f for f in frames if f["box"] is not None)
        plain = client.get(f"{base}/{shopper}/steps/{first['step']}.png?highlight=false")
        marked = client.get(f"{base}/{shopper}/steps/{first['step']}.png")
        assert plain.status_code == marked.status_code == 200 and plain.content != marked.content
        with Image.open(io.BytesIO(plain.content)) as image:
            assert image.size == (first["width"], first["height"])
    assert client.get(f"{base}/nobody/playback").status_code == 404
