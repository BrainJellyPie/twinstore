"""A shopper's visit as an animated GIF: one frame per step, the last held longer."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from tests.server.test_online_rival_api import PID, _site, _wait, client  # noqa: F401  (fixture)


def test_a_visit_downloads_as_one_gif_frame_per_step(client: TestClient) -> None:
    site = _site(client, "pet_store")
    runs = f"/api/projects/{PID}/online/runs"
    status = client.post(runs, json={"site_ids": [site["id"]], "shoppers": 3, "seed": 2, "max_steps": 12,
                                      "mobile_share": 0}).json()
    assert _wait(client, status["run_id"])["status"]["status"] == "completed"
    shopper = "os0001"
    session = client.get(f"{runs}/{status['run_id']}/sessions/0/{shopper}").json()["session"]
    response = client.get(f"{runs}/{status['run_id']}/sessions/0/{shopper}/replay.gif")
    assert response.status_code == 200 and response.headers["content-type"] == "image/gif"
    assert f'filename="{status["run_id"]}-0-{shopper}.gif"' in response.headers["content-disposition"]
    with Image.open(io.BytesIO(response.content)) as gif:
        assert gif.n_frames == len(session["steps"]) and gif.width == 640
        durations = []
        for frame in range(gif.n_frames):
            gif.seek(frame)
            durations.append(gif.info["duration"])
    assert durations[-1] == 3 * durations[0]
    assert client.get(f"{runs}/{status['run_id']}/sessions/0/nobody/replay.gif").status_code == 404
