"""Canvas drag-and-drop snapping helpers."""

from .guides import (
    MAX_THRESHOLD,
    MIN_THRESHOLD,
    PIXEL_TOLERANCE,
    SnapError,
    apply_snap,
    edges,
    guide_candidates,
    resolve_conflict,
    snap_batch,
    snap_offset,
    snap_spacing,
    validate,
)

__all__ = [
    "MAX_THRESHOLD",
    "MIN_THRESHOLD",
    "PIXEL_TOLERANCE",
    "SnapError",
    "apply_snap",
    "edges",
    "guide_candidates",
    "resolve_conflict",
    "snap_batch",
    "snap_offset",
    "snap_spacing",
    "validate",
]
