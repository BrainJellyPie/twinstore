"""Shelf capture: photograph a real shelf face, get a Parastore planogram.

Pipeline (pure functions; the application layer adds storage, jobs and model resolution):
`bands` (shelf levels from straight shelf edges) → `detect` (facings and gaps: classic CV,
Grounding DINO or VLM grounding) → `recognize` (identical facings grouped, one VLM read per
product) → `catalog_match` (category, price units, typical-price fallback) → `planogram`
(rack slots, replaced faces or new racks). `synthetic` renders benchmark shelves with exact ground truth.
"""

from .detect import (
    ClassicDetector,
    Detection,
    FacingDetector,
    GroundingDinoDetector,
    VLMGroundingDetector,
    gdino_available,
)
from .overlay import render_overlay
from .pipeline import CaptureRun, capture_shelf
from .planogram import (
    PlacementReport,
    add_capture_racks,
    display_name,
    replace_rack_face,
    sku_for,
)
from .recognize import VLMLabeler

__all__ = [
    "CaptureRun",
    "ClassicDetector",
    "Detection",
    "FacingDetector",
    "GroundingDinoDetector",
    "PlacementReport",
    "VLMGroundingDetector",
    "VLMLabeler",
    "add_capture_racks",
    "capture_shelf",
    "display_name",
    "gdino_available",
    "render_overlay",
    "replace_rack_face",
    "sku_for",
]
