from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from .types import FACE_OFFSETS as _FACE_OFFSETS, Face, Position, Shape

# All slot-capable racks have exactly 4 levels; level count is fixed and empty slots are sparse.

type _SideTileKey = tuple[object, ...]
_SIDE_TILE_CACHE: dict[_SideTileKey, frozenset[Position]] = {}
_SIDE_TILE_CACHE_MAX = 100_000
RACK_LEVELS: Final[int] = 4


class RackType(StrEnum):
    SHELF = "shelf"
    FRIDGE = "fridge"
    COUNTER = "counter"   # checkout face = unlocked exposed side face (see service_access_tiles)
    ENTRANCE = "entrance"
    EXIT = "exit"


PASSTHROUGH_TYPES: frozenset[RackType] = frozenset({RackType.ENTRANCE, RackType.EXIT})

SLOT_CAPABLE_TYPES: frozenset[RackType] = frozenset({RackType.SHELF, RackType.FRIDGE, RackType.COUNTER})


class BlockFace(BaseModel):
    block: int
    face: Face


class SlotItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str
    name: str
    price: int = 0  # unit: US cents (e.g. 549 = $5.49)
    promo: str = ""
    image_url: str | None = None  # backend fills this from manifest; falls back to placeholder when absent


class Slot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block: int
    face: Face
    level: int = Field(default=1, ge=1, le=RACK_LEVELS)
    # Max 4 SKUs per face (spec rev 5 decision 10); 5+ raises ValidationError at the domain layer.
    items: list[SlotItem] = Field(default_factory=list[SlotItem], max_length=4)


class Rack(BaseModel):
    id: str
    type: RackType
    shape: Shape
    position: Position
    rotation: Literal[0, 90, 180, 270] = 0
    levels: int = RACK_LEVELS  # domain only uses RACK_LEVELS, but kept for frontend round-trip fidelity
    dwell_min: int = 5   # seconds
    dwell_max: int = 30  # seconds
    rack_name: str = ""
    rack_desc: str = ""
    rack_decoration_desc: str = ""
    # Frontend asset selector. 'c' is the wall-end variant (shelf only).
    design_variant: Literal["a", "b", "c"] = "a"
    locked_faces: list[BlockFace] = []
    slots: list[Slot] = []

    @property
    def rotated_shape(self) -> Shape:
        s = self.shape
        for _ in range((self.rotation // 90) % 4):
            s = _rotate_90(s)
        return s

    @property
    def block_cells(self) -> list[Position]:
        s = self.rotated_shape
        return [(r, c) for r in range(len(s)) for c in range(len(s[0])) if s[r][c]]

    @property
    def occupied_positions(self) -> list[Position]:
        px, py = self.position
        return [(px + c, py + r) for r, c in self.block_cells]

    def valid_faces(self, block_index: int) -> list[Face]:
        s = self.rotated_shape
        cells = self.block_cells
        if block_index >= len(cells):
            return []
        r, c = cells[block_index]
        rows, cols = len(s), len(s[0])
        faces: list[Face] = []
        if self.type not in SLOT_CAPABLE_TYPES:
            return faces
        if r == 0 or s[r - 1][c] == 0:
            faces.append(Face.N)
        if r == rows - 1 or s[r + 1][c] == 0:
            faces.append(Face.S)
        if c == 0 or s[r][c - 1] == 0:
            faces.append(Face.W)
        if c == cols - 1 or s[r][c + 1] == 0:
            faces.append(Face.E)
        return faces

    def with_rotation(self, new_rotation: Literal[0, 90, 180, 270]) -> "Rack":
        """Update rotation only (frontend asset render angle).

        spec rev 4 decision 4: slot.face / locked_faces are NOT remapped.
        Multi-cell racks raise ValueError to prevent silent corruption.
        """
        if len(self.block_cells) > 1:
            raise ValueError(
                "Multi-cell rotation is no longer supported; "
                "grid editor produces 1x1 only."
            )
        if new_rotation == self.rotation:
            return self.model_copy()
        return self.model_copy(update={"rotation": new_rotation})

    def access_tiles(self, grid_size: tuple[int, int]) -> set[Position]:
        """Adjacent tiles of every valid side face, excluding OOB and self-occupied cells."""
        return self._side_tiles(grid_size, exclude_locked=False)

    def service_access_tiles(self, grid_size: tuple[int, int]) -> set[Position]:
        """Adjacent tiles of unlocked side faces — the faces where checkout/service can occur."""
        return self._side_tiles(grid_size, exclude_locked=True)

    def _side_tiles(self, grid_size: tuple[int, int], *, exclude_locked: bool) -> set[Position]:
        # Pure function of the rack geometry; memoized because routing asks for it
        # tens of thousands of times per run. The key covers every input, so an edited
        # rack (moved, rotated, re-shaped, faces locked) gets a fresh entry.
        key = (
            self.type, tuple(tuple(row) for row in self.shape), self.rotation, self.position,
            tuple((bf.block, bf.face) for bf in self.locked_faces) if exclude_locked else (),
            grid_size, exclude_locked,
        )
        cached = _SIDE_TILE_CACHE.get(key)
        if cached is not None:
            return set(cached)
        tiles = self._compute_side_tiles(grid_size, exclude_locked=exclude_locked)
        if len(_SIDE_TILE_CACHE) > _SIDE_TILE_CACHE_MAX:
            _SIDE_TILE_CACHE.clear()
        _SIDE_TILE_CACHE[key] = frozenset(tiles)
        return tiles

    def _compute_side_tiles(self, grid_size: tuple[int, int], *, exclude_locked: bool) -> set[Position]:
        w, h = grid_size
        locked: set[tuple[int, Face]] = {(bf.block, bf.face) for bf in self.locked_faces} if exclude_locked else set()
        px, py = self.position
        occupied = set(self.occupied_positions)
        tiles: set[Position] = set()
        for idx, (r, c) in enumerate(self.block_cells):
            for face in self.valid_faces(idx):
                if (idx, face) in locked:
                    continue
                dx, dy = _FACE_OFFSETS[face]
                tile = (px + c + dx, py + r + dy)
                if 0 <= tile[0] < w and 0 <= tile[1] < h and tile not in occupied:
                    tiles.add(tile)
        return tiles

    def accepts_face_at(self, tile: Position, face: Face, grid_size: tuple[int, int]) -> bool:
        """True iff `tile` is an access tile of this rack on the given `face`."""
        w, h = grid_size
        px, py = self.position
        occupied = set(self.occupied_positions)
        dx, dy = _FACE_OFFSETS[face]
        for idx, (r, c) in enumerate(self.block_cells):
            if face not in self.valid_faces(idx):
                continue
            candidate = (px + c + dx, py + r + dy)
            if candidate != tile:
                continue
            if not (0 <= candidate[0] < w and 0 <= candidate[1] < h):
                continue
            if candidate in occupied:
                continue
            return True
        return False



class RackPreset(BaseModel):
    type: RackType
    rack_name: str = ""
    label: str
    shape: Shape
    locked_faces: list[BlockFace] = []


def has_accessible_tile(
    shape: Shape, position: Position, grid_size: tuple[int, int],
    occupied: set[Position],
) -> bool:
    """Test placement feasibility from shape + position alone (no Rack instance).

    Exhaustively checks exposed side faces for an in-bounds, unoccupied access tile.
    Used by generators before a Rack object exists.
    """
    w, h = grid_size
    px, py = position
    rows, cols = len(shape), len(shape[0])
    cells = [(r, c) for r in range(rows) for c in range(cols) if shape[r][c]]
    body = {(px + c, py + r) for r, c in cells}
    for r, c in cells:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nr, nc = r + dy, c + dx
            if 0 <= nr < rows and 0 <= nc < cols and shape[nr][nc]:
                continue
            tx, ty = px + c + dx, py + r + dy
            if 0 <= tx < w and 0 <= ty < h and (tx, ty) not in body and (tx, ty) not in occupied:
                return True
    return False


def _rotate_90(shape: Shape) -> Shape:
    rows, cols = len(shape), len(shape[0])
    return [[shape[rows - 1 - j][i] for j in range(rows)] for i in range(cols)]
