"""What a shopper sees from the door: a store directory (text) and a top-down directory map (image).

The directory groups racks by their category label ("Drink 1", "Drink 2" → "Drink") with a few
example products and the price range, so a planning model can only ask for things the store
sells. The map is a clean floor plan: racks as blocks colored by type with their sign, red
ribbons on racks that carry promoted items, the entrance and the checkout. Both are
deterministic for a given store, so planning calls stay cacheable and paired comparisons exact.
"""

import base64
import io
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw

from store_emulator.domain.rack import Rack, RackType, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.prompting import display_price

from .shelf_render import load_font, text_color, wrap_text

_TRAILING_INDEX = re.compile(r"[\s\d#_\-]+$")

_RACK_COLORS: dict[RackType, tuple[int, int, int]] = {
    RackType.FRIDGE: (96, 150, 210),
    RackType.SHELF: (214, 178, 122),
    RackType.COUNTER: (120, 124, 132),
}
_PROMO_RED = (214, 32, 39)


def category_label(rack: Rack) -> str:
    """Rack sign without its running number: "Drink 2" → "Drink"; unnamed racks use their type."""
    label = _TRAILING_INDEX.sub("", rack.rack_name.strip())
    return label or ("Fridge" if rack.type == RackType.FRIDGE else "Shelf")


@dataclass(frozen=True)
class DirectoryEntry:
    label: str
    rack_ids: tuple[str, ...]
    examples: tuple[str, ...]
    min_price: int
    max_price: int
    promos: tuple[tuple[str, str], ...]  # (product name, promo label)
    items: int


def store_directory(store: Store, *, examples: int = 3) -> list[DirectoryEntry]:
    """Categories present in the store, in rack order. Examples: promoted items first, then eye
    and waist level, then the rest; prices over every stocked item of the category."""
    groups: dict[str, list[Rack]] = {}
    for rack in store.product_racks:
        if rack.type == RackType.COUNTER:
            continue
        groups.setdefault(category_label(rack).lower(), []).append(rack)
    out: list[DirectoryEntry] = []
    for racks in groups.values():
        entries: list[tuple[int, SlotItem]] = []
        for rack in racks:
            for slot in rack.slots:
                entries.extend((slot.level, item) for item in slot.items)
        if not entries:
            continue
        ranked = sorted(entries, key=lambda e: (not e[1].promo, {3: 0, 2: 1, 4: 2, 1: 3}.get(e[0], 4)))
        names: list[str] = []
        for _, item in ranked:
            if item.name not in names:
                names.append(item.name)
            if len(names) >= examples:
                break
        promos: list[tuple[str, str]] = []
        for _, item in entries:
            if item.promo and (item.name, item.promo) not in promos:
                promos.append((item.name, item.promo))
        prices = [item.price for _, item in entries]
        out.append(DirectoryEntry(
            label=category_label(racks[0]), rack_ids=tuple(r.id for r in racks), examples=tuple(names),
            min_price=min(prices), max_price=max(prices), promos=tuple(promos), items=len(entries),
        ))
    return out


def directory_text(directory: list[DirectoryEntry], currency: str, *, max_promos: int = 3) -> str:
    """One line per category: "- Drink: Pepsi 20oz, Arizona Green Tea 23oz, … ($1.29–$3.29); on sale: …"."""
    lines: list[str] = []
    for entry in directory:
        low, high = display_price(entry.min_price, currency), display_price(entry.max_price, currency)
        price = low if entry.min_price == entry.max_price else f"{low}–{high}"
        line = f"- {entry.label}: {', '.join(entry.examples)} ({price})"
        if entry.promos:
            line += "; on sale: " + ", ".join(f"{name} {promo}" for name, promo in entry.promos[:max_promos])
        lines.append(line)
    return "\n".join(lines)


@dataclass(frozen=True)
class StoreMapView:
    png: bytes
    size: tuple[int, int]

    def data_url(self) -> str:
        return "data:image/png;base64," + base64.b64encode(self.png).decode("ascii")


def render_store_map(store: Store, *, width: int = 512) -> StoreMapView:
    """Top-down directory map of the store, as seen on the sign by the door."""
    gw, gh = store.grid_size
    margin, title_h, legend_h = 14, 40, 34
    cell = max(24, (width - 2 * margin) // max(1, gw))
    grid_w, grid_h = cell * gw, cell * gh
    width = max(width, grid_w + 2 * margin)
    height = margin + title_h + grid_h + legend_h + margin
    img = Image.new("RGB", (width, height), (246, 244, 239))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((margin, margin, width - margin, margin + title_h - 8), radius=6, fill=(38, 50, 66))
    draw.text((margin + 12, margin + (title_h - 8) // 2), f"{store.name or 'Store'} — store directory",
              font=load_font(18, bold=True), fill=(255, 255, 255), anchor="lm")

    ox, oy = (width - grid_w) // 2, margin + title_h
    draw.rectangle((ox, oy, ox + grid_w, oy + grid_h), fill=(232, 230, 224), outline=(60, 60, 60), width=3)
    for x in range(1, gw):
        draw.line((ox + x * cell, oy, ox + x * cell, oy + grid_h), fill=(220, 218, 211))
    for y in range(1, gh):
        draw.line((ox, oy + y * cell, ox + grid_w, oy + y * cell), fill=(220, 218, 211))

    label_size = max(10, min(15, cell // 5))
    small_size = max(9, min(12, cell // 6))
    label_font = load_font(label_size, bold=True)
    small_font = load_font(small_size, bold=True)
    doors: dict[tuple[int, int], list[str]] = {}
    for rack in store.racks:
        cells = rack.occupied_positions
        if not cells:
            continue
        if rack.type in (RackType.ENTRANCE, RackType.EXIT):
            for pos in cells:
                doors.setdefault(pos, []).append("IN" if rack.type == RackType.ENTRANCE else "OUT")
            continue
        color = _RACK_COLORS.get(rack.type, (180, 180, 180))
        for x, y in cells:
            draw.rectangle((ox + x * cell + 2, oy + y * cell + 2, ox + (x + 1) * cell - 2, oy + (y + 1) * cell - 2),
                           fill=color, outline=(50, 50, 50), width=1)
        x0 = ox + min(x for x, _ in cells) * cell
        y0 = oy + min(y for _, y in cells) * cell
        x1 = ox + (max(x for x, _ in cells) + 1) * cell
        y1 = oy + (max(y for _, y in cells) + 1) * cell
        if any(item.promo for slot in rack.slots for item in slot.items):
            draw.rectangle((x0 + 3, y0 + 3, x1 - 3, y0 + 7 + small_size), fill=_PROMO_RED)
            draw.text(((x0 + x1) // 2, y0 + 5), "SALE", font=small_font, fill=(255, 255, 255), anchor="mt")
        counter = rack.type == RackType.COUNTER
        name = "Checkout" if counter else (rack.rack_name or category_label(rack))
        font, size = (small_font, small_size) if counter else (label_font, label_size)
        lines = wrap_text(draw, name, font, x1 - x0 - 6, max_lines=3)
        line_h = size + 2
        ty = (y0 + y1) // 2 - line_h * len(lines) // 2 + 4
        for i, line in enumerate(lines):
            draw.text(((x0 + x1) // 2, ty + i * line_h), line, font=font, fill=text_color(color), anchor="mt")
    for (x, y), kinds in doors.items():
        box = (ox + x * cell + 2, oy + y * cell + 2, ox + (x + 1) * cell - 2, oy + (y + 1) * cell - 2)
        draw.rectangle(box, fill=(46, 160, 67), outline=(20, 90, 30), width=2)
        text = "/".join(sorted(set(kinds), key=lambda k: k != "IN"))
        draw.text(((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), text, font=label_font, fill=(255, 255, 255), anchor="mm")

    ly = oy + grid_h + 10
    lx = ox
    legend: list[tuple[tuple[int, int, int], str]] = [
        (_RACK_COLORS[RackType.SHELF], "Shelf"), (_RACK_COLORS[RackType.FRIDGE], "Fridge"),
        (_RACK_COLORS[RackType.COUNTER], "Checkout"), (_PROMO_RED, "Promotion"), ((46, 160, 67), "Entrance"),
    ]
    legend_font = load_font(13)
    for color, text in legend:
        draw.rectangle((lx, ly, lx + 16, ly + 16), fill=color, outline=(50, 50, 50))
        draw.text((lx + 22, ly + 8), text, font=legend_font, fill=(30, 30, 30), anchor="lm")
        lx += 30 + int(draw.textlength(text, font=legend_font))

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)
    return StoreMapView(png=buf.getvalue(), size=(width, height))
