"""Explicit edits to placed products; prices use integer currency minor units."""
from typing import Annotated, Self
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_PRICE = 9_007_199_254_740_991
type ProductLayoutId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


class ProductEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    price: int | None = Field(default=None, ge=0, le=MAX_PRICE, strict=True)
    promo: str | None = Field(default=None, max_length=200)

    @field_validator("name", "promo", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def meaningful(self) -> Self:
        if not self.sku.strip():
            raise ValueError("SKU must not be blank")
        if self.name is None and self.price is None and self.promo is None:
            raise ValueError("Specify at least one product field")
        return self


class ProductEditsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    edits: list[ProductEdit] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({edit.sku for edit in self.edits}) != len(self.edits):
            raise ValueError("Edit each SKU only once")
        return self


class ProductEditsSave(ProductEditsRequest):
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class ProductRow(BaseModel):
    sku: str
    names: list[str]
    prices: list[int]
    promos: list[str]
    placements: int
    racks: list[str]


class ProductCatalog(BaseModel):
    source_sha256: str
    currency: str
    products: list[ProductRow]


class ProductChange(BaseModel):
    before: ProductRow
    after: ProductRow
    changed_placements: int


class ProductEditsPreview(BaseModel):
    changes: list[ProductChange]
    changed_placements: int


class ProductEditsSaved(BaseModel):
    setup_id: str
    changed_placements: int


class ProductEditsRecord(BaseModel):
    product_edits_request: ProductEditsSave
    product_edits_result: ProductEditsSaved


class ProductEditsReceipt(BaseModel):
    source_id: str
