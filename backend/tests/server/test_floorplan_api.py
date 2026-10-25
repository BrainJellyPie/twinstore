"""Floor plan import through the API: a sketch becomes a new active draft layout."""

import io
import base64
import sys
from pathlib import Path

import pytest
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from test_floorplan import sketch

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _png() -> bytes:
    buf = io.BytesIO()
    sketch(seed=1).save(buf, format="PNG")
    return buf.getvalue()


def test_sketch_becomes_a_layout(client):
    res = client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("my-store.png", _png(), "image/png")},
                      data={"reader": "auto", "model": "none"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reading"]["reader"] == "classic" and body["racks"] > 5
    assert body["setup"]["name"] == "floor plan (my-store)"
    setup = client.get(f"/api/projects/{PID}/setups/{body['setup_id']}").json()
    assert setup["store"]["grid_size"] == list(body["grid_size"])
    assert client.get(f"/api/projects/{PID}").json()["state"]["activeSetupId"] == body["setup_id"]


def test_bad_uploads_are_rejected(client):
    assert client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("x.png", b"not an image", "image/png")}).status_code == 400
    pdf = client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("plan.pdf", b"%PDF-1.4 ...", "application/pdf")})
    assert pdf.status_code in (400, 422)
    assert client.post("/api/projects/nope/floorplan", files={"plan": ("x.png", _png(), "image/png")}).status_code == 404


def _pdf() -> bytes:
    buf = io.BytesIO()
    cover = Image.new("RGB", (300, 200), "red")
    cover.save(buf, format="PDF", save_all=True, append_images=[sketch(seed=1).convert("RGB")])
    return buf.getvalue()


def test_preview_selects_and_rotates_pages_without_creating_a_layout(client):
    before = client.get(f"/api/projects/{PID}/setups").json()
    response = client.post(f"/api/projects/{PID}/floorplan/preview", files={"plan": ("plan.pdf", _pdf(), "application/pdf")},
                           data={"page_number": "1", "rotation": "90"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page_count"] == 2 and body["page_number"] == 1 and body["rotation"] == 90
    assert body["width"] == 400 and body["height"] == 600
    image = Image.open(io.BytesIO(base64.b64decode(body["image"].split(",")[1])))
    red, green, blue = image.convert("RGB").getpixel((100, 100))
    assert red > 240 and green < 10 and blue < 10
    assert client.get(f"/api/projects/{PID}/setups").json() == before


def test_selected_pdf_plan_page_becomes_the_layout(client):
    response = client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("plan.pdf", _pdf(), "application/pdf")},
                           data={"reader": "classic", "page_number": "2", "rotation": "90"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_page"] == 2 and body["source_pages"] == 2 and body["source_rotation"] == 90
    assert body["racks"] > 5
    assert any("page 2 of 2" in note for note in body["notes"])


@pytest.mark.parametrize("data", [{"page_number": "0"}, {"page_number": "3"}, {"rotation": "45"}])
def test_invalid_page_selection_preserves_layouts(client, data):
    before = client.get(f"/api/projects/{PID}/setups").json()
    for endpoint in ["floorplan", "floorplan/preview"]:
        response = client.post(f"/api/projects/{PID}/{endpoint}", files={"plan": ("plan.pdf", _pdf(), "application/pdf")}, data=data)
        assert response.status_code == 422, response.text
    assert client.get(f"/api/projects/{PID}/setups").json() == before


def test_image_preview_respects_exif_orientation(client):
    image = Image.new("RGB", (40, 20), "white")
    exif = Image.Exif()
    exif[274] = 6  # camera rotated clockwise
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    response = client.post(f"/api/projects/{PID}/floorplan/preview", files={"plan": ("photo.jpg", buffer.getvalue(), "image/jpeg")})
    assert response.status_code == 200, response.text
    assert response.json()["width"] == 20 and response.json()["height"] == 40


@pytest.mark.parametrize("reader", ["auto", "vlm"])
def test_known_kind_spelling_keeps_model_geometry_in_the_saved_layout(client, monkeypatch, reader):
    import copy
    from store_emulator.application import floorplan
    from store_emulator.domain.config import LLMConfig
    from tests.engine.test_floorplan_model_geometry import GOOD

    payload = copy.deepcopy(GOOD)
    payload.update(width_m=20, depth_m=10)
    for fixture in payload["fixtures"]:
        fixture["kind"] = f" {fixture['kind'].title()} "

    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            return schema.model_validate(payload)

    monkeypatch.setattr(floorplan, "capture_llm_config", lambda *args: LLMConfig(model="openai/floorplan-spelling"))
    monkeypatch.setattr(floorplan, "LiteLLMClient", lambda *args: Model())
    response = client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("store.png", _png(), "image/png")},
                           data={"reader": reader, "model": "scripted"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reading"]["reader"] == "openai/floorplan-spelling"
    assert (body["reading"]["width_m"], body["reading"]["depth_m"]) == (20, 10)
    assert len(body["reading"]["fixtures"]) == 3 and body["grid_size"] == [16, 8]
    assert not any("unavailable" in note for note in body["notes"])
    saved = client.get(f"/api/projects/{PID}/setups/{body['setup_id']}").json()
    assert saved["store"]["grid_size"] == [16, 8]
    assert client.get(f"/api/projects/{PID}").json()["state"]["activeSetupId"] == body["setup_id"]
