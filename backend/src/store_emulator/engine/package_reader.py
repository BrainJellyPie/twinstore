"""A product image read by a vision model: the name, brand and size printed on the pack, and which product of the
layout it shows. Replaces names guessed from file names ("IMG_2041") with what the pack actually says."""

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from decimal import Decimal
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
observation supports them. Nutrition or serving reference amounts are not the package net size.
Do not invent missing package details. Return {"shelf_product": ""} if no exact match
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
        normalized = re.sub(r"(?<=\w)\s*[×*]\s*(?=\d)", " x ", normalized)
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
    multiplied_quantities = re.compile(
        r"(?<![\d.,])(?:(?:\d+ x )+\d+(?:[.,]\d+)? [^\W\d_]+(?: x \d+(?![\d.,]))*"
        r"|\d+(?:[.,]\d+)? [^\W\d_]+(?: x \d+(?![\d.,]))+)"
    )
    # Keep the whole expression together, including 2 x 500 ml x 3. Otherwise
    # a trailing count can bind to a reordered brand name as if it were a unit.
    label_tokens = re.compile(multiplied_quantities.pattern + r"|\d+(?:[.,]\d+)? [^\W\d_]+|[^ ]+")
    observed_tokens = Counter(label_tokens.findall(observed))
    # A serving/reference amount can be printed beside the net size. Reject
    # contradictory amounts, including exact conversions between metric units.
    quantities = re.compile(r"(\d+(?:[.,]\d+)?) ([^\W\d_]+)")
    metric_units: dict[str, tuple[str, int]] = {
        "ml": ("ml", 0), "cl": ("ml", 1), "dl": ("ml", 2), "l": ("ml", 3),
        "mg": ("g", -3), "g": ("g", 0), "kg": ("g", 3),
    }

    def metric_quantity(amount: str, unit: str) -> tuple[str, Decimal] | None:
        scale = metric_units.get(unit)
        # 1,000 / 1.000 can be either a grouped integer or a decimal. Do not
        # infer a cross-unit contradiction from an ambiguous printed separator.
        if scale is None or re.fullmatch(r"[1-9]\d{0,2}[.,]\d{3}", amount):
            return None
        value = Decimal(amount.replace(",", ".")).as_tuple()
        assert isinstance(value.exponent, int)  # The quantity regex permits only finite decimal numbers.
        # Shifting a base-10 exponent is exact even beyond Decimal's current precision.
        return scale[0], Decimal((value.sign, value.digits, value.exponent + scale[1]))

    net_quantities: dict[str, set[Decimal]] = {}
    metric_net: dict[str, set[Decimal]] = {}
    for amount, unit in quantities.findall(printed_words(reading.size)):
        net_quantities.setdefault(unit, set()).add(Decimal(amount.replace(",", ".")))
        metric = metric_quantity(amount, unit)
        if metric is not None:
            metric_net.setdefault(metric[0], set()).add(metric[1])

    def agrees_with_net_size(words: str) -> bool:
        for amount, unit in quantities.findall(words):
            if unit in net_quantities and Decimal(amount.replace(",", ".")) not in net_quantities[unit]:
                return False
            metric = metric_quantity(amount, unit)
            if metric is not None and metric[0] in metric_net and metric[1] not in metric_net[metric[0]]:
                return False
        return True

    # A visible multipack cannot be linked to its single-unit catalog entry,
    # even though every word in the single-unit name appears on the pack.
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
              if (words := printed_words(name.strip()[:120])) and agrees_with_net_size(words) and
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
