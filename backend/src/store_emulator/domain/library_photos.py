"""Reviewed assignments of existing package photos to placed products."""
from typing import Annotated, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator

type PhotoDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PhotoAsset(BaseModel):
    asset_id: str
    name: str
    sku: str
    version: PhotoDigest
    image_url: str


class PhotoProduct(BaseModel):
    sku: str
    names: list[str]
    image_urls: list[str]
    placements: int


class PhotoOptions(BaseModel):
    source_sha256: PhotoDigest
    assets: list[PhotoAsset]
    products: list[PhotoProduct]


class PhotoAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(min_length=1, max_length=200)
    asset_id: str = Field(pattern=r"^pkg_[a-zA-Z0-9_-]{1,120}$")
    version: PhotoDigest


class PhotoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_sha256: PhotoDigest
    assignments: list[PhotoAssignment] = Field(min_length=1, max_length=100)
    replace_existing: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({a.sku for a in self.assignments}) != len(self.assignments):
            raise ValueError("Choose one image per SKU")
        if any(not a.sku.strip() for a in self.assignments):
            raise ValueError("SKU must not be blank")
        return self


class PhotoSave(PhotoRequest):
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class PhotoChange(PhotoProduct):
    asset_name: str
    image_url: str


class PhotoPreview(BaseModel):
    changes: list[PhotoChange]
    changed_placements: int


class PhotoSaved(BaseModel):
    setup_id: str
    changed_placements: int


class PhotoRecord(BaseModel):
    library_photos_request: PhotoSave
    library_photos_result: PhotoSaved
