"""Check exact assortments against world-space geometry and independent copies."""
import pytest

from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.rack_copy import choices, copy_products


@pytest.mark.parametrize("shape", [
    [[1]], [[1, 1]], [[1], [1]], [[1, 1], [1, 0]],
    [[1, 0, 1], [1, 1, 1]], [[1, 1, 1], [1, 0, 1], [1, 1, 1]],
])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("kind", ["shelf", "fridge"])
@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_every_exposed_face_is_copied_without_rotating_or_normalizing_products(shape, rotation, kind, level):
    source = Rack(id="source", type=kind, shape=shape, rotation=rotation, position=(3, 3))
    # Same SKU deliberately has distinct placement values, including free goods,
    # safe-integer limits and Unicode. Reuse must not collapse it into a SKU map.
    products = [SlotItem(sku="茶_한글", name=f"Pack {i}", price=price,
                         regular_price=9007199254740991 - i, promo="✨" * i,
                         image_url=f"/image-{i}.png")
                for i, price in enumerate([0, 1, 9007199254740990, 9007199254740991])]
    source.slots = [Slot(block=b, face=f, level=level, items=products)
                    for b in range(len(source.block_cells)) for f in source.valid_faces(b)]
    # An enclosed hole has no shopper access; leave its faces unstocked.
    from store_emulator.engine.starter_fill import available_faces
    targets = [Rack(id=f"target_{i}", type=kind, shape=source.rotated_shape, position=(10 + i * 7, 3))
               for i in range(2)]
    store = Store(id="store", name="Exact copy", type="convenience", currency="CAD", grid_size=(24, 14),
                  racks=[Rack(id="door", type="entrance", shape=[[1]], position=(0, 13)), source, *targets])
    available = available_faces(store)[source.id]
    source.slots = [s for s in source.slots if (s.block, s.face) in available]
    original = store.model_dump(mode="json")
    result, report = copy_products(store, source.id, [r.id for r in targets])
    assert report.placements_added == len(source.slots) * 4 * 2
    assert store.model_dump(mode="json") == original
    assert report.slots == source.slots
    for target in result.racks[2:]:
        assert target.rotation == 0
        assert target.slots == source.slots
    # Editing either child destination cannot change its sibling or the source.
    result.racks[2].slots[0].items[0].price = 812
    result.racks[2].slots[0].items.reverse()
    assert result.racks[3].slots == source.slots
    assert result.racks[1].slots == source.slots
    assert store.model_dump(mode="json") == original


@pytest.mark.parametrize("source_face", ["N", "S", "E", "W"])
@pytest.mark.parametrize("locked_face", ["N", "S", "E", "W"])
@pytest.mark.parametrize("kind", ["shelf", "fridge"])
def test_only_the_faces_actually_being_copied_must_be_unlocked(source_face, locked_face, kind):
    source = Rack(id="source", type=kind, shape=[[1]], position=(2, 2),
                  slots=[Slot(block=0, face=source_face, items=[SlotItem(sku="sku", name="Product")])])
    target = Rack(id="target", type=kind, shape=[[1]], position=(5, 2),
                  locked_faces=[{"block": 0, "face": locked_face}],
                  slots=[Slot(block=0, face=locked_face, level=4, items=[])])
    store = Store(id="s", name="s", type="convenience", grid_size=(9, 9), racks=[
        Rack(id="door", type="entrance", shape=[[1]], position=(0, 8)), source, target])
    _, options = choices(store, "source")
    option = next(r for r in options if r.id == "target")
    original = store.model_dump(mode="json")
    if source_face == locked_face:
        assert option.reason and "locked" in option.reason
        with pytest.raises(ValueError, match="locked"):
            copy_products(store, "source", ["target"])
    else:
        assert option.reason is None
        result, report = copy_products(store, "source", ["target"])
        assert report.placements_added == 1
        assert result.racks[2].slots[0] == target.slots[0]
        assert result.racks[2].slots[1] == source.slots[0]
    assert store.model_dump(mode="json") == original
