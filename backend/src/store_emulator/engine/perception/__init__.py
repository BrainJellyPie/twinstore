"""Visual perception: rendering what a shopper sees, for vision-language shopper engines."""

from .shelf_render import MarkedItem, ShelfView, face_slots, render_face
from .store_map import (
    DirectoryEntry,
    StoreMapView,
    category_label,
    directory_text,
    render_store_map,
    store_directory,
)

__all__ = [
    "DirectoryEntry",
    "MarkedItem",
    "ShelfView",
    "StoreMapView",
    "category_label",
    "directory_text",
    "face_slots",
    "render_face",
    "render_store_map",
    "store_directory",
]
