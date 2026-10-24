"""Large fixtures must not rescan their whole shape once per occupied block."""

from collections import Counter

import pytest

from store_emulator.domain.rack import BlockFace, Rack, RackType, _SIDE_TILE_CACHE
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.starter_fill import available_faces
from store_emulator.engine.validation import list_blocked_faces


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("operation", ["blocked", "starter", "access", "service", "accept"])
def test_shape_scan_work_stays_bounded_per_fixture(monkeypatch, rotation, operation):
    rows, cols = 20, 35
    rack = Rack(id="large", type=RackType.SHELF, shape=[[1]*cols for _ in range(rows)], position=(2, 2), rotation=rotation)
    store = Store(id="store", name="Large fixture", type="test", grid_size=(40, 40), racks=[
        Rack(id="entrance", type=RackType.ENTRANCE, shape=[[1]], position=(0, 0)), rack,
    ])
    before = store.model_dump()
    getter = Rack.block_cells.fget
    scans = Counter()

    def bounded_cells(self):
        # A full shape enumeration has work proportional to its area. Repeating
        # it per block is quadratic; allow ample room for the independent passes.
        scans[self.id] += 1
        assert scans[self.id] <= 24, "Repeated full-shape scans make face analysis quadratic"
        return getter(self)

    _SIDE_TILE_CACHE.clear()
    monkeypatch.setattr(Rack, "block_cells", property(bounded_cells))
    if operation == "blocked":
        result = list_blocked_faces(store)
        assert len(result) == 4*rows*cols - 2*(rows+cols)
        assert all(row.reasons == ["occluded"] for row in result)
    elif operation == "starter":
        assert len(available_faces(store)[rack.id]) == 2*(rows+cols)
    elif operation == "access":
        assert len(rack.access_tiles(store.grid_size)) == 2*(rows+cols)
    elif operation == "service":
        assert len(rack.service_access_tiles(store.grid_size)) == 2*(rows+cols)
    else:
        assert not rack.accepts_face_at((-1, -1), Face.N, store.grid_size)
    assert store.model_dump() == before


@pytest.mark.parametrize("kind", [RackType.SHELF, RackType.FRIDGE, RackType.COUNTER])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_holes_locked_faces_and_edits_keep_their_geometry(kind, rotation):
    rack = Rack(id="ring", type=kind, shape=[[1, 1, 1], [1, 0, 1], [1, 1, 1]], position=(2, 2), rotation=rotation,
                locked_faces=[BlockFace(block=0, face=Face.N)])
    store = Store(id="store", name="Ring", type="test", grid_size=(8, 8), racks=[
        Rack(id="entrance", type=RackType.ENTRANCE, shape=[[1]], position=(0, 0)), rack,
    ])
    records = list_blocked_faces(store)
    assert Counter(reason for row in records for reason in row.reasons) == {"occluded": 16, "unreachable": 4, "locked": 1}
    assert len(rack.access_tiles(store.grid_size)) == 13
    assert len(rack.service_access_tiles(store.grid_size)) == 12
    assert rack.accepts_face_at((3, 3), Face.S, store.grid_size, block=1)
    assert not rack.accepts_face_at((3, 2), Face.E, store.grid_size, block=0)
    if kind != RackType.COUNTER:
        assert len(available_faces(store)[rack.id]) == 11
    rack.position = (0, 2)
    moved = list_blocked_faces(store)
    assert Counter(reason for row in moved for reason in row.reasons) == {
        "occluded": 16, "unreachable": 4, "locked": 1, "out_of_bounds": 3,
    }
    assert len(rack.access_tiles(store.grid_size)) == 10
    rack.locked_faces = []
    assert rack.service_access_tiles(store.grid_size) == rack.access_tiles(store.grid_size)


@pytest.mark.parametrize("kind", [RackType.TABLE, RackType.ENTRANCE, RackType.EXIT])
def test_furniture_and_passage_roles_stay_distinct(kind):
    rack = Rack(id="fixture", type=kind, shape=[[1, 1]], position=(2, 2))
    assert not rack.accepts_face_at((1, 2), Face.W, (8, 8))
    assert len(rack.access_tiles((8, 8))) == (6 if kind == RackType.TABLE else 0)
    assert len(rack.service_access_tiles((8, 8))) == (6 if kind == RackType.TABLE else 0)
