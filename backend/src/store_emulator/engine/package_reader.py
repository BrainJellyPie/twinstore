"""A product image read by a vision model: the name, brand and size printed on the pack, and which product of the
layout it shows. Replaces names guessed from file names ("IMG_2041") with what the pack actually says."""

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from store_emulator.engine.capture.detect import image_data_url

MAX_LISTED = 150


class VisionLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...

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


class _PackResponse(BaseModel):
    # Require complete generated observations, while retaining safe defaults for
    # providers that omit unknown optional metadata instead of using empty text.
    model_config = ConfigDict(json_schema_extra={"required": ["printed_text", "name", "brand", "size", "category", "confidence"]})
    printed_text: str = Field(max_length=400, description="Only letters and numbers visibly printed on the image, or ''")
    name: str = Field(default="", max_length=80)
    brand: str = Field(default="", max_length=40)
    size: str = Field(default="", max_length=30)
    category: str = Field(default="", max_length=40)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0,
        description="Confidence as a fraction, never a percentage", json_schema_extra={"enum": [0, 0.25, 0.5, 0.75, 1]})

    @field_validator("printed_text", "name", "brand", "size", "category", mode="before")
    @classmethod
    def _unknown_print(cls, value: object) -> object:
        return "" if value is None else value

PACK_PROMPT = """Read only the product image. First transcribe printed_text: letters and numbers visibly printed
on the package. If there is no readable writing, printed_text must be "". Never invent or estimate label text.
Then give name (brand-free product type, flavour and any visible size), brand (the printed brand, not the product
type), size (net size as printed) and category. Do not estimate size from the package's appearance.
If printed_text is empty, brand and size must be empty. The name can describe the visible product type.
Include printed_text, name, brand, size, category and confidence. Unknown text must be "", not null.
There is no store catalog in this observation step.
Confidence is a fraction: choose 0, 0.25, 0.5, 0.75 or 1. Never use 100 or another percentage."""

MATCH_PROMPT = """Match the observed package to at most one listed store product. The observation is evidence;
the candidate list is not evidence of what was printed. Only match the same brand, variant and size when the
observation supports them. Do not invent missing package details. Return {"shelf_product": ""} if no exact match
is supported or multiple products remain possible. Otherwise copy the listed name into shelf_product.
For a product name longer than 120 characters, copy its first 120 characters only when that prefix identifies one
listed product. If several names share that prefix, leave shelf_product empty instead of guessing."""


async def read_pack(llm: VisionLLM, image: Image.Image, products: Sequence[str]) -> PackReading:
    url, _ = image_data_url(image.convert("RGB"), max_side=768, fmt="JPEG")
    reading = await llm.generate_structured_with_image_async(
        _PackResponse, PACK_PROMPT, "Transcribe only the package in this image.", url, max_retries=2, seed=0,
    )
    # Tiny VLMs copy candidate names into their supposed OCR. Keep the catalog
    # out of image observation entirely; require supporting transcribed words for links.
    target = ""
    def printed_words(value: str) -> str:
        # Keep word boundaries, but allow capitalization, punctuation and 500ml/500 ml.
        normalized = unicodedata.normalize("NFKC", value).casefold()
        normalized = re.sub(r"(?<=\d)\s*[×*]\s*(?=\d)", " x ", normalized)
        return " ".join(re.findall(r"[^\W\d_]+|\d+(?:[.,]\d+)?", normalized))

    observed = printed_words(reading.printed_text)
    brand_words, size_words = printed_words(reading.brand), printed_words(reading.size)
    if not brand_words or f" {brand_words} " not in f" {observed} ":
        reading.brand = ""
    if not size_words or f" {size_words} " not in f" {observed} ":
        reading.size = ""
    # Labels and catalog display names can put the same brand/size words in
    # different orders. Require every full token, including repeated words,
    # and keep quantities together: "500 g 100 ml" does not prove "500 ml".
    # The separate matching call still decides whether the identity agrees.
    label_tokens = re.compile(r"\d+(?:[.,]\d+)? [^\W\d_]+|[^ ]+")
    observed_tokens = Counter(label_tokens.findall(observed))
    # A visible multipack cannot be linked to its single-unit catalog entry,
    # even though every word in the single-unit name appears on the pack.
    multiplied_quantities = re.compile(r"(?<![\d.,])(?:\d+ x )+\d+(?:[.,]\d+)? [^\W\d_]+")
    observed_packs = set(multiplied_quantities.findall(observed))
    counted_packs = re.compile(
        r"(?<![\w.,])(?:(\d+)\s*-?\s*(?:packs?|pk|count|ct|입|개입|本入り|個入り|bottles?|cans?|jars?|병|캔|本|缶)"
        r"|pack\s+of\s+(\d+))(?!\w)",
        re.IGNORECASE,
    )
    def pack_counts(value: str) -> set[str]:
        # Match before splitting letters from digits: B6 PACK is not six packs.
        return {printed_words(match.group()) for match in counted_packs.finditer(unicodedata.normalize("NFKC", value))
                if any(int(count) > 1 for count in match.groups() if count)}

    observed_counts = pack_counts(reading.printed_text)
    # Bound the matching prompt after evidence filtering: unrelated early
    # catalog entries must not hide an observed product later in the store.
    listed = [name for name in dict.fromkeys(products)
              if (words := printed_words(name.strip()[:120])) and
              observed_packs <= set(multiplied_quantities.findall(words)) and
              observed_counts <= pack_counts(name.strip()[:120]) and
              (f" {words} " in f" {observed} " or Counter(label_tokens.findall(words)) <= observed_tokens)][:MAX_LISTED]
    if listed:
        names: list[JsonValue] = ["", *dict.fromkeys(name.strip()[:120] for name in listed)]

        class PackMatch(BaseModel):
            shelf_product: str = Field(default="", max_length=120, json_schema_extra={"enum": names})

            @field_validator("shelf_product", mode="before")
            @classmethod
            def unknown_match(cls, value: object) -> object:
                return "" if value is None else value

        matched = await llm.generate_structured_async(PackMatch, MATCH_PROMPT,
            json.dumps({"observation": reading.model_dump(), "store_products": listed},
                       ensure_ascii=False), max_retries=2, seed=0)
        target = matched.shelf_product
    known = {p.strip().casefold(): p for p in products if p.strip()}
    supported = {p.strip().casefold() for p in listed}
    key = target.strip().casefold()
    if len(target) == 120:
        matches = [name for name in known if name.startswith(key)]
        shelf = known[matches[0]] if key and len(matches) == 1 and matches[0] in supported else ""
    else:
        shelf = known.get(key, "") if key in supported else ""
    return PackReading.model_validate({**reading.model_dump(),
        "name": reading.name.strip(), "brand": reading.brand.strip(), "size": reading.size.strip(),
        "category": reading.category.strip(), "shelf_product": shelf,
    })
