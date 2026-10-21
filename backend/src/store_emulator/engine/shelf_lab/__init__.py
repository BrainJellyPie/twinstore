"""Shelf Lab: controlled experiments on photographed shelves (see domain.shelf_lab).

`edits` (counterfactual photo edits with exact ground truth) → `sim2real` (the same shoppers on the
photo and on its rendered twin) → `audit` (field photo vs reference face, priced by paired simulation).
"""

from .edits import EditOutcome, apply_edits, synth_package
from .sim2real import TwinViews, build_views, glance_panel, summarize

__all__ = [
    "EditOutcome",
    "TwinViews",
    "apply_edits",
    "build_views",
    "glance_panel",
    "summarize",
    "synth_package",
]
