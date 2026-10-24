"""Shelf capture: a photographed shelf face turned into a planogram.

Coordinates are pixels of the stored capture image (EXIF orientation applied), origin top-left.
Bands are numbered from the top of the photo (band 0 = highest shelf); `level` is the Parastore
rack level the band maps to (1 = bottom … RACK_LEVELS = top).
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

type CaptureDetector = Literal["auto", "gdino", "vlm", "classic"]
type CaptureRackType = Literal["shelf", "fridge"]
type CaptureState = Literal["pending", "running", "completed", "failed"]


class Box(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2


class ShelfBand(BaseModel):
    """Product zone of one shelf: the products standing on the shelf edge at `bottom`."""
    index: int                      # 0 = top band
    level: int = 1                  # Parastore level (1 = bottom)
    top: float                      # vertical extent of the product zone (image pixels, at mid-width)
    bottom: float
    # The zone as a quadrilateral in image pixels (clockwise from top-left): shelves may be tilted.
    polygon: list[tuple[float, float]] = []


class ShelfItemLabel(BaseModel):
    """What the vision-language model reads off one product (crop + price-tag strip)."""
    # Field order matters for small models filling a JSON grammar: read the tag text before the number.
    name: str = Field(default="", max_length=80, description="product name as printed, without brand")
    brand: str = Field(default="", max_length=40)
    size: str = Field(default="", max_length=20, description="package size if printed on the package, else empty")
    category: str = Field(default="", max_length=40, description="e.g. soft drink, chips, instant noodles")
    price_text: str = Field(default="", max_length=24, description="the price tag text exactly as printed")
    price: float | None = Field(default=None, description="price on the shelf tag, as a number; null if unreadable")
    confidence: int = Field(default=5, ge=0, le=10)

    @field_validator("name", "brand", "size", "category", "price_text", mode="before")
    @classmethod
    def _unknown_text(cls, value: object) -> object:
        return "" if value is None else value


class CaptureItem(BaseModel):
    """One product on the shelf: a run of identical facings."""
    id: str
    band: int
    level: int
    order: int                      # left-to-right position within the band
    facings: int = Field(default=1, ge=1)
    boxes: list[Box] = []           # one per facing, image coordinates
    sku: str = ""
    name: str = ""
    brand: str = ""
    size: str = ""
    category: str = ""              # catalog category key (engine.layout_gen.catalog), "" if unknown
    raw_category: str = ""          # category text as read by the model
    price: int | None = None        # currency minor unit (USD cents, KRW won)
    price_estimated: bool = False   # True when the tag was unreadable and a typical price was used
    price_text: str = ""
    confidence: int = 0             # model confidence 0–10 (0 = not recognized)
    labeled: bool = False           # a model (or the user) named this item


class CaptureGap(BaseModel):
    """An empty stretch of shelf (out-of-stock hole)."""
    band: int
    level: int
    box: Box
    facings: float = 1.0            # width in typical facings


class CaptureOptions(BaseModel):
    detector: CaptureDetector = "auto"
    model: str = ""                 # model reference ("llamacpp:local", "gemini:…"); "" = app default VLM
    currency: str = "USD"
    rack_type: CaptureRackType = "shelf"
    label: str = ""


class CaptureResult(BaseModel):
    image_size: tuple[int, int]     # (width, height) of the stored image
    tilt_deg: float = 0.0           # estimated camera roll; bands are horizontal after undoing it
    detector: str = ""              # detector actually used
    detection_sources: dict[str, int] = {}  # facings per source: gdino / vlm / classic / fill (gap re-check)
    model: str = ""
    currency: str = "USD"
    rack_type: CaptureRackType = "shelf"
    bands: list[ShelfBand] = []
    items: list[CaptureItem] = []
    gaps: list[CaptureGap] = []
    dominant_category: str = ""
    notes: list[str] = []
    timings: dict[str, float] = {}
    vlm_calls: int = 0
    edited: bool = False

    @property
    def facings(self) -> int:
        return sum(i.facings for i in self.items)


class CaptureStatus(BaseModel):
    capture_id: str
    status: CaptureState
    stage: str = ""                 # queued | detecting | reading | planogram | done
    progress: float = 0.0           # 0–1
    error: str = ""
    options: CaptureOptions = CaptureOptions()
    image_name: str = ""
    image_size: tuple[int, int] = (0, 0)
    created_at: str = ""
    finished_at: str = ""
    items: int = 0
    facings: int = 0
    gaps: int = 0
    levels: int = 0
    applied_setup_ids: list[str] = []
    upload_sha256: str = ""  # request content identity for safe upload retries
