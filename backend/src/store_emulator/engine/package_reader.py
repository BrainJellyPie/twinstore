"""A product image read by a vision model: the name, brand and size printed on the pack, and which product of the
layout it shows. Replaces names guessed from file names ("IMG_2041") with what the pack actually says."""

from collections.abc import Sequence
from typing import Protocol

from PIL import Image
from pydantic import BaseModel, Field, field_validator

from store_emulator.engine.capture.detect import image_data_url

MAX_LISTED = 150


class VisionLLM(Protocol):
    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...


class PackReading(BaseModel):
    name: str = Field(default="", max_length=80, description="the product as a shopper would name it, with flavour and size")
    brand: str = Field(default="", max_length=40)
    size: str = Field(default="", max_length=30, description="net size as printed, e.g. '500 ml'")
    category: str = Field(default="", max_length=40, description="e.g. 'Green tea', 'Potato chips'")
    shelf_product: str = Field(default="", description="the full listed store product this pack is, or ''")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("name", "brand", "size", "category", "shelf_product", mode="before")
    @classmethod
    def _unknown_text(cls, value: object) -> object:
        return "" if value is None else value


class _PackResponse(PackReading):
    shelf_product: str = Field(default="", max_length=120, description="the listed store product, or its first 120 characters, or ''")

PACK_PROMPT = """You read product packaging. From the image, give the product's name as a shopper would say it
(brand-free, with flavour or variant and size), its brand, the net size as printed and a short category. If the store's
product list below has this exact product (same brand, variant and size), copy its name into shelf_product; otherwise
leave shelf_product empty. For any unreadable or unknown text field, use an empty string instead of null.
For a product name longer than 120 characters, copy its first 120 characters only when that prefix identifies one
listed product. If several names share that prefix, leave shelf_product empty instead of guessing.
Do not guess text you cannot read; say how sure you are in confidence."""


async def read_pack(llm: VisionLLM, image: Image.Image, products: Sequence[str]) -> PackReading:
    url, _ = image_data_url(image.convert("RGB"), max_side=768, fmt="JPEG")
    listed = "; ".join(list(dict.fromkeys(products))[:MAX_LISTED]) or "none given"
    reading = await llm.generate_structured_with_image_async(
        _PackResponse, PACK_PROMPT, f"Store products: {listed}", url, max_retries=2, seed=0,
    )
    known = {p.casefold(): p for p in products}
    key = reading.shelf_product.strip().casefold()
    if len(reading.shelf_product) == 120:
        matches = [name for name in known if name.startswith(key)]
        shelf = known[matches[0]] if key and len(matches) == 1 else ""
    else:
        shelf = known.get(key, "")
    return PackReading.model_validate({**reading.model_dump(),
        "name": reading.name.strip(), "brand": reading.brand.strip(), "size": reading.size.strip(),
        "category": reading.category.strip(), "shelf_product": shelf,
    })
