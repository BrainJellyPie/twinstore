"""After an update the browser must load the new UI, not the page it kept from the last version."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from store_emulator.server.main import mount_web_ui


def _client(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<script src="/assets/index-abc123.js"></script>')
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    app = FastAPI()
    mount_web_ui(app, dist.resolve())
    return TestClient(app)


def test_page_is_asked_for_again_on_every_visit(tmp_path):
    client = _client(tmp_path)
    for path in ("/", "/projects/proj_1/setups", "/index.html", "/settings"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "index-abc123.js" in response.text
        assert response.headers["cache-control"] == "no-cache", path


def test_hashed_scripts_are_kept(tmp_path):
    response = _client(tmp_path).get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]
    assert response.headers["content-type"].startswith("text/javascript")


def test_other_files_are_revalidated(tmp_path):
    response = _client(tmp_path).get("/favicon.svg")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_api_paths_are_not_the_page(tmp_path):
    assert _client(tmp_path).get("/api/nothing").status_code == 404
