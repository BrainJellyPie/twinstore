"""Delayed pack readings preserve newer edits, deletion, and ambiguous product links."""
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest
from PIL import Image
from filelock import FileLock

from store_emulator.application import shelf_lab
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.store import Store


@pytest.fixture
def pack(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pid = 'test_project'
    write_json(metadata_path(pid), {'name': 'Test'})
    data = io.BytesIO()
    Image.new('RGB', (12, 16), 'green').save(data, format='PNG')
    asset = shelf_lab.upload_package(pid, data.getvalue(), 'tea.png', name='Original name', brand='Original brand', remove_background=False)
    monkeypatch.setattr(shelf_lab, 'assistive_vision_model', lambda *args: '')
    monkeypatch.setattr(shelf_lab, 'capture_llm_config', lambda config, model: config.engines.vlm_glance.llm)
    return pid, asset.asset_id, SimulationConfig()


def reader(monkeypatch, *, action=lambda: None, shelf_product=''):
    class Fake:
        async def generate_structured_with_image_async(self, response_model, *args, **kwargs):
            action()
            return response_model.model_validate({'printed_text': 'Read brand Read tea ' + shelf_product, 'name': 'Read tea', 'brand': 'Read brand'})

        async def generate_structured_async(self, response_model, *args, **kwargs):
            return response_model.model_validate({'shelf_product': shelf_product})
    monkeypatch.setattr(shelf_lab, 'LiteLLMClient', lambda config: Fake())


@pytest.mark.parametrize('update', [{'name': 'My new name'}, {'brand': 'My new brand'}, {'sku': 'My chosen SKU'}])
def test_a_read_does_not_overwrite_metadata_edited_while_the_model_was_working(pack, monkeypatch, update):
    pid, aid, config = pack
    png = shelf_lab.package_path(pid, aid)
    image = png.read_bytes()
    current = {}
    def edit():
        shelf_lab.update_package(pid, aid, shelf_lab.PackageUpdate(**update))
        current.update(read_json(png.with_suffix('.json')))
    reader(monkeypatch, action=edit)
    with pytest.raises(AppError) as raised:
        shelf_lab.read_package(pid, aid, config=config)
    assert raised.value.status_code == 409
    assert read_json(png.with_suffix('.json')) == current
    assert png.read_bytes() == image


def test_a_deleted_image_does_not_get_its_metadata_resurrected_by_a_late_read(pack, monkeypatch):
    pid, aid, config = pack
    png = shelf_lab.package_path(pid, aid)
    reader(monkeypatch, action=lambda: shelf_lab.delete_package(pid, aid))
    with pytest.raises(AppError) as raised:
        shelf_lab.read_package(pid, aid, config=config)
    assert raised.value.status_code == 404
    assert not png.exists() and not png.with_suffix('.json').exists()


@pytest.mark.parametrize('same_sku', [False, True])
@pytest.mark.parametrize('same_case', [False, True])
def test_only_an_unambiguous_product_name_can_be_linked(pack, monkeypatch, same_sku, same_case):
    pid, aid, config = pack
    store = Store.model_validate({'id': 'test', 'name': 'Test', 'type': 'convenience', 'grid_size': [8, 6], 'racks': [
        {'id': 'r1', 'type': 'shelf', 'shape': [[1]], 'position': [1, 1], 'rack_name': 'Tea', 'slots': [
            {'block': 0, 'face': 'S', 'items': [{'sku': 'A', 'name': 'Green Tea 500 ml', 'price': 100}]}]},
        {'id': 'r2', 'type': 'shelf', 'shape': [[1]], 'position': [3, 1], 'rack_name': 'Other tea', 'slots': [
            {'block': 0, 'face': 'S', 'items': [{'sku': 'A' if same_sku else 'B', 'name': 'Green Tea 500 ml' if same_case else 'GREEN TEA 500 ML', 'price': 100}]}]},
    ]})
    monkeypatch.setattr(shelf_lab, '_load_store', lambda *args: store)
    reader(monkeypatch, shelf_product='green tea 500 ml')
    result = shelf_lab.read_package(pid, aid, setup_id='test_setup', config=config)
    assert result.asset.name == 'Read tea'
    assert result.linked is same_sku
    assert result.asset.sku == ('A' if same_sku else '')


def test_an_existing_manual_product_link_is_kept(pack, monkeypatch):
    pid, aid, config = pack
    shelf_lab.update_package(pid, aid, shelf_lab.PackageUpdate(sku='manual-sku'))
    reader(monkeypatch)
    result = shelf_lab.read_package(pid, aid, config=config)
    assert not result.linked and result.asset.sku == 'manual-sku'


@pytest.mark.parametrize('operation', ['read', 'update', 'delete'])
def test_concurrent_metadata_writers_use_the_same_lock(pack, monkeypatch, operation):
    pid, aid, config = pack
    png = shelf_lab.package_path(pid, aid)
    before = read_json(png.with_suffix('.json'))
    reader(monkeypatch)
    with FileLock(png.with_suffix('.lock'), timeout=0):
        with pytest.raises(AppError) as raised:
            if operation == 'read':
                shelf_lab.read_package(pid, aid, config=config)
            elif operation == 'update':
                shelf_lab.update_package(pid, aid, shelf_lab.PackageUpdate(name='Competing edit'))
            else:
                shelf_lab.delete_package(pid, aid)
    assert raised.value.status_code == 409
    assert png.exists() and read_json(png.with_suffix('.json')) == before


def test_an_older_read_cannot_replace_a_newer_read(pack, monkeypatch):
    pid, aid, config = pack
    started, release = Event(), Event()
    count_lock = Lock()
    count = 0
    class Fake:
        async def generate_structured_with_image_async(self, response_model, *args, **kwargs):
            nonlocal count
            with count_lock:
                count += 1
                ordinal = count
            if ordinal == 1:
                started.set()
                assert await asyncio.to_thread(release.wait, 10)
            return response_model.model_validate({'printed_text': '', 'name': 'Older reading' if ordinal == 1 else 'Newer reading'})
    monkeypatch.setattr(shelf_lab, 'LiteLLMClient', lambda config: Fake())
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(shelf_lab.read_package, pid, aid, config=config)
        try:
            assert started.wait(10)
            current = shelf_lab.read_package(pid, aid, config=config)
            assert current.asset.name == 'Newer reading'
        finally:
            release.set()
        with pytest.raises(AppError) as raised:
            old.result(timeout=10)
    assert raised.value.status_code == 409
    assert shelf_lab.list_packages(pid)[0].name == 'Newer reading'
