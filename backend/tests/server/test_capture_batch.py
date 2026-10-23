"""Real placement/storage API workflow with explicit offline recognition fixtures."""

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from store_emulator.application.capture import save_capture
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data, read_setup, setup_path
from store_emulator.application.storage.images import load_manifest
from store_emulator.domain.capture import (
    Box,
    CaptureItem,
    CaptureOptions,
    CaptureResult,
    ShelfBand,
)
from store_emulator.domain.rack import Rack, RackType
from store_emulator.domain.store import Store

PID = "proj_67916afd"
ROOT = f"/api/projects/{PID}/captures"
BASE = "setup_batch_base"


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app

    with TestClient(app) as client:
        store = Store(
            id="demo",
            name="Offline base",
            type="convenience",
            currency="USD",
            grid_size=(12, 12),
            racks=[
                Rack(
                    id="entrance", type=RackType.ENTRANCE, shape=[[1]], position=(0, 11)
                ),
                Rack(id="exit", type=RackType.EXIT, shape=[[1]], position=(11, 11)),
                Rack(
                    id="counter", type=RackType.COUNTER, shape=[[1]], position=(10, 0)
                ),
            ],
        )
        base = new_setup_data("Base", None, store.model_dump(mode="json"))
        base["id"] = BASE
        write_json(setup_path(PID, BASE), base)
        ids = []
        for index in range(2):
            result = CaptureResult(
                image_size=(200, 200),
                currency="USD",
                dominant_category="soft_drinks",
                bands=[ShelfBand(index=0, level=1, top=0, bottom=200)],
                items=[
                    CaptureItem(
                        id=f"item{index}",
                        sku=f"photo_sku{index}",
                        name=f"Observed tea {index}",
                        band=0,
                        level=1,
                        order=0,
                        facings=2,
                        price=250 + index,
                        labeled=True,
                        boxes=[
                            Box(x1=5, y1=5, x2=80, y2=170),
                            Box(x1=85, y1=5, x2=160, y2=170),
                        ],
                    )
                ],
            )
            ids.append(
                save_capture(
                    PID,
                    Image.new("RGB", (200, 200), "orange"),
                    f"Shelf {index}.jpg",
                    CaptureOptions(currency="USD"),
                    result,
                ).capture_id
            )
        yield client, {"capture_ids": ids, "setup_id": BASE}, tmp_path


def test_preview_save_reload_products_and_crops_without_touching_sources(workflow):
    client, request, tmp_path = workflow
    before = setup_path(PID, BASE).read_bytes()
    sources = {
        str(p): p.read_bytes()
        for p in (tmp_path / ".data" / PID / "captures").rglob("*")
        if p.is_file()
    }
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert (
        result["placed_items"] == 2
        and result["placed_facings"] == 4
        and result["dropped"] == []
    )
    assert not list(
        setup_path(PID, BASE).parent.glob("setup_batch_" + "a" * 32 + ".json")
    )
    saved = client.post(
        ROOT + "/batch-save",
        json={
            **request,
            "source_sha256": result["source_sha256"],
            "request_id": "a" * 32,
        },
    )
    assert saved.status_code == 200, saved.text
    stored = read_setup(PID, saved.json()["setup_id"])
    reloaded = client.get(f"/api/projects/{PID}/setups/{saved.json()['setup_id']}")
    assert reloaded.status_code == 200, reloaded.text
    resolved = Store.model_validate(reloaded.json()["store"])
    for _, slot in resolved.all_slots:
        for item in slot.items:
            assert item.image_url, "The public layout must resolve its saved crop images"
            item.image_url = None
    assert resolved == Store.model_validate(stored["store"])
    actual = Store.model_validate(stored["store"])
    assert actual == Store.model_validate(result["store"])
    assert {i.sku for _, slot in actual.all_slots for i in slot.items} == {
        "photo_sku0",
        "photo_sku1",
    }
    assert {"photo_sku0", "photo_sku1"}.issubset(load_manifest(PID))
    assert stored["parentId"] == BASE and stored["status"] == "draft"
    assert setup_path(PID, BASE).read_bytes() == before
    assert {
        str(p): p.read_bytes()
        for p in (tmp_path / ".data" / PID / "captures").rglob("*")
        if p.is_file()
    } == sources


def edit_result(tmp_path, cid, change):
    import json

    path = tmp_path / ".data" / PID / "captures" / cid / "result.json"
    raw = json.loads(path.read_text())
    change(raw)
    write_json(path, raw)


def prepare_save(client, request, token="a"):
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 200, response.text
    return {
        **request,
        "source_sha256": response.json()["source_sha256"],
        "request_id": token * 32,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"capture_ids": []},
        {"capture_ids": ["x"] * 21},
        {"capture_ids": ["x", "x"]},
        {"capture_ids": ["../bad"]},
        {"capture_ids": ["x" * 300]},
        {"setup_id": "x" * 300},
        {"setup_id": "../bad"},
        {"extra": True},
    ],
)
def test_request_limits(workflow, change):
    client, request, _ = workflow
    response = client.post(ROOT + "/batch-preview", json={**request, **change})
    assert response.status_code == 422, response.text


def test_legacy_layout_inherits_project_currency(workflow):
    client, request, _ = workflow
    base = read_setup(PID, BASE)
    base["store"]["currency"] = None
    write_json(setup_path(PID, BASE), base)
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 200, response.text
    assert response.json()["store"]["currency"] == "USD"


def test_missing_price_is_flagged_for_review(workflow):
    client, request, tmp_path = workflow
    edit_result(
        tmp_path,
        request["capture_ids"][0],
        lambda r: r["items"][0].update(
            price=None, price_estimated=False, labeled=False
        ),
    )
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 200, response.text
    assert (
        response.json()["estimated_prices"] == 1
        and response.json()["unrecognized_items"] == 1
    )


@pytest.mark.parametrize("target", ["capture", "store"])
def test_stale_preview_does_not_save(workflow, target):
    client, request, tmp_path = workflow
    form = prepare_save(client, request)
    if target == "capture":
        edit_result(
            tmp_path,
            request["capture_ids"][0],
            lambda r: r["items"][0].update(price=333),
        )
    else:
        base = read_setup(PID, BASE)
        base["store"]["name"] = "Changed"
        write_json(setup_path(PID, BASE), base)
    response = client.post(ROOT + "/batch-save", json=form)
    assert response.status_code == 409 and "changed" in response.text
    assert not setup_path(PID, "setup_batch_" + "a" * 32).exists()


def test_replay_after_changed_sources_and_conflicting_token(workflow):
    client, request, tmp_path = workflow
    form = prepare_save(client, request)
    first = client.post(ROOT + "/batch-save", json=form)
    assert first.status_code == 200
    edit_result(
        tmp_path, request["capture_ids"][0], lambda r: r["items"][0].update(price=555)
    )
    assert client.post(ROOT + "/batch-save", json=form).json() == first.json()
    conflict = client.post(
        ROOT + "/batch-save",
        json={**form, "capture_ids": list(reversed(form["capture_ids"]))},
    )
    assert conflict.status_code == 409
    assert (
        len(
            list(setup_path(PID, BASE).parent.glob("setup_batch_" + "a" * 32 + ".json"))
        )
        == 1
    )


def test_partial_placement_is_previewed_but_cannot_be_saved(workflow):
    client, request, tmp_path = workflow
    edit_result(
        tmp_path,
        request["capture_ids"][0],
        lambda r: r.update(
            items=[
                {
                    **r["items"][0],
                    "id": f"p{i}",
                    "sku": f"sku{i}",
                    "name": f"variant {i}",
                    "facings": 1,
                }
                for i in range(7)
            ]
        ),
    )
    result = client.post(ROOT + "/batch-preview", json=request)
    assert result.status_code == 200, result.text
    assert result.json()["dropped"]
    response = client.post(
        ROOT + "/batch-save",
        json={
            **request,
            "source_sha256": result.json()["source_sha256"],
            "request_id": "b" * 32,
        },
    )
    assert response.status_code == 409 and "do not fit" in response.text
    assert not setup_path(PID, "setup_batch_" + "b" * 32).exists()


def test_nonready_missing_and_wrong_currency_fail_without_writes(workflow):
    client, request, tmp_path = workflow
    assert (
        client.post(
            ROOT + "/batch-preview", json={**request, "capture_ids": ["cap_missing"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            ROOT + "/batch-preview", json={**request, "setup_id": "missing"}
        ).status_code
        == 404
    )
    edit_result(tmp_path, request["capture_ids"][0], lambda r: r.update(currency="KRW"))
    assert client.post(ROOT + "/batch-preview", json=request).status_code == 422
    edit_result(
        tmp_path,
        request["capture_ids"][0],
        lambda r: r.update(currency="USD", items=[]),
    )
    assert client.post(ROOT + "/batch-preview", json=request).status_code == 409


def test_lost_acknowledgment_retry_and_concurrent_save_create_one_draft(
    workflow, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from store_emulator.application import capture_batch

    client, request, _ = workflow
    form = prepare_save(client, request)
    original = capture_batch.write_json

    def lost_ack(path, payload):
        original(path, payload)
        raise OSError("simulated lost acknowledgment after atomic save")

    monkeypatch.setattr(capture_batch, "write_json", lost_ack)
    assert client.post(ROOT + "/batch-save", json=form).status_code == 500
    monkeypatch.setattr(capture_batch, "write_json", original)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: client.post(ROOT + "/batch-save", json=form), range(2))
        )
    assert all(r.status_code in (200, 409) for r in responses)
    retried = client.post(ROOT + "/batch-save", json=form)
    assert retried.status_code == 200
    assert (
        len(
            list(setup_path(PID, BASE).parent.glob("setup_batch_" + "a" * 32 + ".json"))
        )
        == 1
    )


def test_exact_names_reuse_sku_but_other_sizes_stay_distinct(workflow):
    client, request, tmp_path = workflow
    edit_result(
        tmp_path,
        request["capture_ids"][1],
        lambda r: r["items"][0].update(name="Observed tea 0"),
    )
    same = client.post(ROOT + "/batch-preview", json=request).json()
    store = Store.model_validate(same["store"])
    assert {i.sku for _, slot in store.all_slots for i in slot.items} == {"photo_sku0"}
    edit_result(
        tmp_path,
        request["capture_ids"][1],
        lambda r: r["items"][0].update(size="500ml", brand="새 브랜드"),
    )
    distinct = client.post(ROOT + "/batch-preview", json=request).json()
    store = Store.model_validate(distinct["store"])
    assert {i.sku for _, slot in store.all_slots for i in slot.items} == {
        "photo_sku0",
        "photo_sku1",
    }


def test_reduced_facings_require_explicit_acceptance(workflow):
    client, request, tmp_path = workflow
    edit_result(
        tmp_path, request["capture_ids"][0], lambda r: r["items"][0].update(facings=24)
    )
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 200
    report = response.json()
    assert (
        report["requested_facings"] == 26
        and report["reduced_facings"] == 20
        and report["placed_facings"] == 6
    )
    form = {**request, "source_sha256": report["source_sha256"], "request_id": "c" * 32}
    assert client.post(ROOT + "/batch-save", json=form).status_code == 409
    assert (
        client.post(
            ROOT + "/batch-save", json={**form, "allow_reduced_facings": "yes"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            ROOT + "/batch-save", json={**form, "allow_reduced_facings": True}
        ).status_code
        == 200
    )


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_stored_prices_are_rejected_instead_of_zero_or_server_error(
    workflow, value
):
    client, request, tmp_path = workflow
    edit_result(
        tmp_path, request["capture_ids"][0], lambda r: r["items"][0].update(price=value)
    )
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 409, response.text


def test_nonfinite_crop_is_rejected_with_a_reviewable_error(workflow):
    client, request, tmp_path = workflow
    edit_result(
        tmp_path,
        request["capture_ids"][0],
        lambda r: r["items"][0]["boxes"][0].update(x1=float("nan")),
    )
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 409, response.text


def test_zero_price_unicode_and_facing_limits(workflow):
    client, request, tmp_path = workflow
    edit_result(
        tmp_path,
        request["capture_ids"][0],
        lambda r: r["items"][0].update(price=0, name="차 & café 🍵", facings=1),
    )
    response = client.post(ROOT + "/batch-preview", json=request)
    assert response.status_code == 200
    items = [
        item
        for rack in response.json()["store"]["racks"]
        for slot in rack["slots"]
        for item in slot["items"]
    ]
    assert any(i["name"] == "차 & café 🍵" and i["price"] == 0 for i in items)
    edit_result(
        tmp_path, request["capture_ids"][0], lambda r: r["items"][0].update(facings=25)
    )
    assert client.post(ROOT + "/batch-preview", json=request).status_code == 422
    edit_result(
        tmp_path,
        request["capture_ids"][0],
        lambda r: r.update(
            items=[{**r["items"][0], "id": str(i), "facings": 24} for i in range(84)]
        ),
    )
    assert client.post(ROOT + "/batch-preview", json=request).status_code == 422


@pytest.mark.parametrize("mode", ["batch", "single", "multiple"])
@pytest.mark.parametrize("configured", [False, True])
def test_capture_variants_keep_operating_conditions(workflow, mode, configured):
    from store_emulator.application.setups import run_operations, save_layout_operations
    from store_emulator.domain.operations import OperationsConfig
    client, request, _ = workflow
    operations = OperationsConfig(stock_per_facing=1, backroom_per_product=0,
                                 daily_delivery=False, crew=2) if configured else None
    save_layout_operations(PID, BASE, operations)
    source = setup_path(PID, BASE).read_bytes()
    if mode == "batch":
        response = client.post(ROOT + "/batch-save", json=prepare_save(client, request))
    elif mode == "single":
        response = client.post(ROOT + f"/{request['capture_ids'][0]}/apply",
                               json={"setup_id": BASE, "new_rack": True})
    else:
        response = client.post(ROOT + "/apply", json=request)
    assert response.status_code == 200, response.text
    assert run_operations(PID, response.json()["setup_id"], None, None) == operations
    assert setup_path(PID, BASE).read_bytes() == source
