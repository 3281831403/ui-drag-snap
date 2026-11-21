"""Red tests for the canvas snapping contract.

Every test calls a public stub in :mod:`dragsnap.guides`. The ten defect tests
map one-to-one to the ten bugs listed in the prompt; the final five tests are
cross-cutting combinations.
"""

import pytest

from dragsnap.guides import (
    MAX_THRESHOLD,
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


def _rect(x, y, w, h):
    """Build the plain dict rectangle used by the public API."""
    return {"x": x, "y": y, "w": w, "h": h}


# ---------------------------------------------------------------------------
# One test per defect (10)
# ---------------------------------------------------------------------------


def test_edges_include_right_and_bottom():
    """Defect 1: only the top-left corner was exposed, so right/bottom missed."""
    got = edges(_rect(10, 20, 100, 50))

    assert got["left"] == 10
    assert got["top"] == 20
    assert got["right"] == 110
    assert got["bottom"] == 70


def test_center_guides_use_half_pixel_geometry():
    """Defect 2: centers were derived from an outer frame and were half off."""
    got = edges(_rect(10, 20, 101, 51))

    assert got["center_x"] == pytest.approx(60.5)
    assert got["center_y"] == pytest.approx(45.5)


def test_guide_candidates_dedupe_repeated_lines():
    """Defect 3: duplicate reference lines caused jitter during snapping."""
    moving = _rect(0, 0, 10, 10)
    others = [_rect(20, 0, 10, 10), _rect(20, 40, 10, 10)]

    got = guide_candidates(others, moving)
    pairs = [(candidate["axis"], candidate["value"]) for candidate in got]

    assert len(pairs) == len(set(pairs))
    assert sum(1 for axis, value in pairs if axis == "x" and value == 20.0) == 1
    assert sum(1 for axis, value in pairs if axis == "x" and value == 25.0) == 1
    assert len(got) == 9


def test_snap_offset_picks_nearest_in_threshold():
    """Defect 4: the first in-range line won instead of the nearest line."""
    moving = _rect(0, 0, 10, 10)
    guides = [
        {"axis": "x", "value": 3.0, "kind": "edge"},
        {"axis": "x", "value": 9.0, "kind": "edge"},
    ]

    got = snap_offset(moving, guides, 6.0)

    assert got["hit"] is True
    assert got["dx"] == pytest.approx(-1.0)
    assert got["dy"] == pytest.approx(0.0)


def test_snap_spacing_honours_spacing_argument():
    """Defect 5: a hard-coded 10 px gap ignored the requested spacing."""
    moving = _rect(130, 50, 20, 20)
    other = _rect(80, 50, 20, 20)

    got = snap_spacing(moving, [other], 24.0)

    assert got["hit"] is True
    assert got["dx"] == pytest.approx(-6.0)
    assert got["dy"] == pytest.approx(0.0)


def test_resolve_conflict_keeps_only_priority_axis():
    """Defect 6: both axes were applied, making the element jump diagonally."""
    x_snap = {"dx": 6.0, "dy": 0.0, "hit": True}
    y_snap = {"dx": 0.0, "dy": -4.0, "hit": True}

    got = resolve_conflict(x_snap, y_snap, "x")

    assert got == {"dx": 6.0, "dy": 0.0, "hit": True}


def test_apply_snap_preserves_size():
    """Defect 7: applying an offset resized the rectangle instead of moving it."""
    rect = _rect(10, 20, 30, 40)

    got = apply_snap(rect, {"dx": 5.0, "dy": -7.0, "hit": True})

    assert got == {"x": 15.0, "y": 13.0, "w": 30, "h": 40}
    assert rect == {"x": 10, "y": 20, "w": 30, "h": 40}


def test_validate_flags_out_of_range_threshold():
    """Defect 8: an unchecked threshold made the rectangle always snap."""
    rect = _rect(0, 0, 10, 10)

    assert "threshold out of range" in validate(rect, [], MAX_THRESHOLD + 1.0)
    assert "threshold out of range" in validate(rect, [], -0.1)
    assert "threshold out of range" not in validate(rect, [], 8.0)


def test_snap_batch_isolates_events_and_rolls_back():
    """Defect 9: references leaked between events, and failures were partial."""
    first = _rect(0, 0, 10, 10)
    second = _rect(0, 100, 10, 10)

    batch = snap_batch(
        [
            {"rect": first, "others": [_rect(10, 0, 10, 10)]},
            {"rect": second, "others": []},
        ],
        {"threshold": 4.0},
    )

    assert batch["ok"] is True
    assert len(batch["results"]) == 2
    assert batch["results"][0]["offset"]["hit"] is True
    assert batch["results"][1]["guides"] == []
    assert batch["results"][1]["offset"] == {
        "dx": 0.0,
        "dy": 0.0,
        "hit": False,
    }

    rolled_back = snap_batch(
        [
            {"rect": first, "others": [_rect(10, 0, 10, 10)]},
            {"rect": _rect(0, 0, -5, 10), "others": []},
        ],
        {"threshold": 4.0},
    )

    assert rolled_back["ok"] is False
    assert rolled_back["results"] == []
    assert rolled_back["error"]


def test_guide_candidates_exclude_moving_rectangle():
    """Defect 10: the moving rectangle was its own reference and always hit."""
    moving = _rect(10, 10, 20, 20)

    assert guide_candidates([moving], moving) == []
    assert guide_candidates([dict(moving)], moving) == []
    assert "reference is self" in validate(moving, [dict(moving)], 8.0)


# ---------------------------------------------------------------------------
# Five cross-cutting combinations
# ---------------------------------------------------------------------------


def test_exact_alignment_returns_zero_offset():
    """An inclusive zero threshold still reports a clean exact alignment."""
    moving = _rect(10, 10, 20, 20)
    guides = [
        {"axis": "x", "value": 10.0, "kind": "edge"},
        {"axis": "y", "value": 10.0, "kind": "edge"},
    ]

    got = snap_offset(moving, guides, 0.0)

    assert got == {"dx": 0.0, "dy": 0.0, "hit": True}


def test_guides_beyond_threshold_are_ignored():
    """A line farther away than the threshold must not snap at all."""
    moving = _rect(0, 0, 10, 10)
    guides = [
        {"axis": "x", "value": 20.0, "kind": "edge"},
        {"axis": "y", "value": 30.0, "kind": "edge"},
    ]

    got = snap_offset(moving, guides, 5.0)

    assert got == {"dx": 0.0, "dy": 0.0, "hit": False}


def test_single_rectangle_without_guides_returns_zero():
    """A lone rectangle has no reference lines, so its offset is zero."""
    moving = _rect(3, 4, 5, 6)

    candidates = guide_candidates([], moving)
    got = snap_offset(moving, candidates, 8.0)

    assert candidates == []
    assert got == {"dx": 0.0, "dy": 0.0, "hit": False}


def test_negative_threshold_raises_snap_error():
    """A negative snap distance is invalid rather than an infinite reach."""
    with pytest.raises(SnapError):
        snap_offset(_rect(0, 0, 10, 10), [], -0.5)


def test_snap_batch_success_preserves_order():
    """A fully successful batch keeps the caller's event order unchanged."""
    events = [
        {"rect": _rect(40, 0, 10, 10), "others": [_rect(30, 0, 10, 10)]},
        {"rect": _rect(10, 100, 10, 10), "others": []},
    ]

    result = snap_batch(events, {"threshold": 5.0})

    assert result["ok"] is True
    assert [entry["rect"]["x"] for entry in result["results"]] == [40, 10]
    assert result["results"][0]["offset"]["hit"] is True
