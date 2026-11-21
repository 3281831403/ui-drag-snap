"""Smart drag-and-drop snap guides for a two-dimensional canvas.

Coordinate system and contracts
-------------------------------
* The canvas origin is at the top-left, ``x`` grows to the right, and ``y``
  grows downward.
* Every coordinate, size, gap, and snap distance is expressed in
  device-independent pixels (px). Fractional pixels are allowed.
* Two coordinates are treated as equal when their absolute difference is at
  most ``PIXEL_TOLERANCE`` (0.5 px). Snap thresholds are inclusive and are
  also measured in px.
* A rectangle is a plain ``dict`` with numeric keys ``"x"``, ``"y"``, ``"w"``,
  and ``"h"``. Functions return new dictionaries and never mutate their
  arguments unless a docstring explicitly says otherwise.
* The functions below are intentionally unimplemented stubs. Each raises
  ``NotImplementedError`` until the behavior described in its docstring is
  implemented.
"""

from __future__ import annotations

PIXEL_TOLERANCE = 0.5
MIN_THRESHOLD = 0.0
MAX_THRESHOLD = 64.0


class SnapError(ValueError):
    """Raised for an invalid snap request, threshold, priority, or batch."""


_GEOMETRY_KEYS = ("x", "y", "w", "h")


def _same_geometry(a: dict, b: dict) -> bool:
    """Return true when all four geometry fields are within tolerance."""
    try:
        return all(
            abs(a[key] - b[key]) <= PIXEL_TOLERANCE for key in _GEOMETRY_KEYS
        )
    except (KeyError, TypeError):
        return False


def _is_self(reference: dict, rect: dict) -> bool:
    """Return true when *reference* denotes the same rectangle as *rect*."""
    return reference is rect or _same_geometry(reference, rect)


def _valid_threshold(threshold: float) -> bool:
    """Return true when *threshold* is a numeric value in the allowed range."""
    try:
        return MIN_THRESHOLD <= threshold <= MAX_THRESHOLD
    except TypeError:
        return False


def edges(rect: dict) -> dict:
    """Return all six axis-aligned guide coordinates of *rect*.

    The returned dictionary has exactly these keys:

    * ``"left"``: ``rect["x"]``
    * ``"right"``: ``rect["x"] + rect["w"]``
    * ``"top"``: ``rect["y"]``
    * ``"bottom"``: ``rect["y"] + rect["h"]``
    * ``"center_x"``: ``rect["x"] + rect["w"] / 2``
    * ``"center_y"``: ``rect["y"] + rect["h"] / 2``

    All values are in px. Right and bottom edges must be present: the
    top-left corner alone is not sufficient. Center lines use the rectangle's
    actual half width/height, not an outer-frame approximation. The input
    rectangle is not modified.
    """
    x = rect["x"]
    y = rect["y"]
    w = rect["w"]
    h = rect["h"]
    return {
        "left": x,
        "right": x + w,
        "top": y,
        "bottom": y + h,
        "center_x": x + w / 2,
        "center_y": y + h / 2,
    }


def guide_candidates(others: list[dict], moving: dict) -> list[dict]:
    """Collect deduplicated snap lines from *others* for *moving*.

    Each reference rectangle contributes three x-axis lines (left, center_x,
    right) and three y-axis lines (top, center_y, bottom). Every candidate is a
    dictionary of the form::

        {"axis": "x" | "y", "value": <px>, "kind": "edge" | "center"}

    Left/right/top/bottom produce ``"kind": "edge"``; center lines produce
    ``"kind": "center"``.

    The *moving* rectangle itself is never a reference. It is excluded when it
    is the same object or when all four of its geometry fields are equal to
    *moving*'s within ``PIXEL_TOLERANCE`` (0.5 px). Candidates are deduplicated
    by axis: two values on the same axis that are within 0.5 px collapse to the
    first one seen. First-seen order is retained by visiting *others* in
    order, and for each rectangle visiting x lines (left, center_x, right)
    followed by y lines (top, center_y, bottom). All values are in px.
    """
    candidates: list[dict] = []
    seen: dict[str, list[float]] = {"x": [], "y": []}

    for other in others:
        if _is_self(other, moving):
            continue
        reference = edges(other)
        for axis, keys, kind in (
            ("x", ("left", "center_x", "right"), ("edge", "center", "edge")),
            ("y", ("top", "center_y", "bottom"), ("edge", "center", "edge")),
        ):
            for key, line_kind in zip(keys, kind):
                value = reference[key]
                if any(abs(value - seen_value) <= PIXEL_TOLERANCE
                       for seen_value in seen[axis]):
                    continue
                seen[axis].append(value)
                candidates.append(
                    {"axis": axis, "value": value, "kind": line_kind}
                )

    return candidates


def snap_offset(rect: dict, guides: list[dict], threshold: float) -> dict:
    """Return the nearest in-threshold translation for *rect*.

    ``guides`` is a list of candidate dictionaries with ``"axis"`` (``"x"`` or
    ``"y"``) and ``"value"`` in px. For the x axis, each candidate is compared
    with the moving rectangle's left, center_x, and right lines; for the y axis
    it is compared with top, center_y, and bottom. On each axis the candidate
    with the smallest absolute px difference wins; an exact tie goes to the
    candidate with the lower coordinate. The returned correction is
    ``guide_value - moving_line`` and must be the nearest line, not merely the
    first line that happens to be within range.

    ``threshold`` is the maximum inclusive snap distance in px and must satisfy
    ``MIN_THRESHOLD <= threshold <= MAX_THRESHOLD``; a value outside that range
    raises :class:`SnapError` instead of snapping unconditionally.

    Returns ``{"dx": <px>, "dy": <px>, "hit": <bool>}``. An axis with no
    in-range candidate contributes ``0.0``. ``hit`` is true when at least one
    axis snapped, including an exact alignment whose correction is 0.0.
    """
    if not _valid_threshold(threshold):
        raise SnapError("threshold out of range")

    reference = edges(rect)
    moving_lines = {
        "x": (reference["left"], reference["center_x"], reference["right"]),
        "y": (reference["top"], reference["center_y"], reference["bottom"]),
    }

    result = {"dx": 0.0, "dy": 0.0, "hit": False}

    for axis, out_key in (("x", "dx"), ("y", "dy")):
        best = None  # (abs_diff, guide_value, correction)
        for guide in guides:
            if guide.get("axis") != axis:
                continue
            value = guide["value"]
            for line in moving_lines[axis]:
                diff = abs(value - line)
                if diff > threshold:
                    continue
                key = (diff, value)
                if best is None or key < best[0]:
                    best = (key, value - line)

        if best is not None:
            result[out_key] = float(best[1])
            result["hit"] = True

    return result


def snap_spacing(rect: dict, others: list[dict], spacing: float) -> dict:
    """Snap *rect* to an equal gap next to an overlapping neighbor.

    ``spacing`` is the desired gap in px and must be greater than zero;
    otherwise :class:`SnapError` is raised. A reference only participates on an
    axis when the two rectangles overlap on the perpendicular axis (a positive
    overlap, not merely touching). For the x axis, eligible placements put
    *rect* immediately to the right of the reference at
    ``other.right + spacing`` or immediately to the left at
    ``other.left - spacing - rect.w``. The placement with the smaller absolute
    ``dx`` wins. The y axis works analogously with top/bottom and ``rect.h``.

    The requested ``spacing`` is authoritative; no fixed 10 px default may be
    substituted. No threshold is applied. Returns
    ``{"dx": <px>, "dy": <px>, "hit": <bool>}`` with 0.0 for an axis that has no
    eligible placement. All distances are in px.
    """
    if spacing <= 0:
        raise SnapError("spacing must be greater than zero")

    result = {"dx": 0.0, "dy": 0.0, "hit": False}

    for axis, out_key, start_key, size_key in (
        ("x", "dx", "x", "w"),
        ("y", "dy", "y", "h"),
    ):
        best = None  # (abs_dx, correction)
        for other in others:
            if _is_self(other, rect):
                continue
            other_edges = edges(other)

            # Eligibility requires a positive overlap on the perpendicular axis.
            if axis == "x":
                overlap = min(rect["y"] + rect["h"], other_edges["bottom"]) - max(
                    rect["y"], other_edges["top"]
                )
            else:
                overlap = min(rect["x"] + rect["w"], other_edges["right"]) - max(
                    rect["x"], other_edges["left"]
                )
            if overlap <= 0:
                continue

            if axis == "x":
                placements = (
                    other_edges["right"] + spacing,
                    other_edges["left"] - spacing - rect["w"],
                )
            else:
                placements = (
                    other_edges["bottom"] + spacing,
                    other_edges["top"] - spacing - rect["h"],
                )

            for target in placements:
                correction = target - rect[start_key]
                key = abs(correction)
                if best is None or key < best[0]:
                    best = (key, correction)

        if best is not None:
            result[out_key] = best[1]
            result["hit"] = True

    return result


def resolve_conflict(x_snap: dict, y_snap: dict, priority: str) -> dict:
    """Resolve simultaneous x/y snap proposals using an axis priority.

    ``x_snap`` and ``y_snap`` are offset dictionaries of the form returned by
    :func:`snap_offset`. ``priority`` must be ``"x"`` or ``"y"``; any other
    value raises :class:`SnapError`. When both axes hit, only the priority
    axis's correction is kept and the other correction is zeroed, so the
    rectangle never jumps in both directions at once. When only one axis hits,
    that axis is used. With no hits, both offsets are 0.0 and ``hit`` is false.

    Returns a new ``{"dx": <px>, "dy": <px>, "hit": <bool>}`` dictionary. All
    values are in px and the inputs are not mutated.
    """
    if priority not in ("x", "y"):
        raise SnapError("priority must be 'x' or 'y'")

    x_hit = bool(x_snap.get("hit"))
    y_hit = bool(y_snap.get("hit"))

    if x_hit and y_hit:
        if priority == "x":
            return {
                "dx": float(x_snap["dx"]),
                "dy": 0.0,
                "hit": True,
            }
        return {
            "dx": 0.0,
            "dy": float(y_snap["dy"]),
            "hit": True,
        }

    if x_hit:
        return {"dx": float(x_snap["dx"]), "dy": 0.0, "hit": True}
    if y_hit:
        return {"dx": 0.0, "dy": float(y_snap["dy"]), "hit": True}
    return {"dx": 0.0, "dy": 0.0, "hit": False}


def apply_snap(rect: dict, offset: dict) -> dict:
    """Translate *rect* by ``offset["dx"]`` and ``offset["dy"]`` in px.

    Returns a new rectangle with the same ``"w"`` and ``"h"`` as the input; a
    snap changes position only and must never resize or stretch the rectangle.
    The original rectangle and offset are not modified.
    """
    return {
        "x": rect["x"] + offset.get("dx", 0.0),
        "y": rect["y"] + offset.get("dy", 0.0),
        "w": rect["w"],
        "h": rect["h"],
    }


def validate(rect: dict, others: list[dict], threshold: float) -> list[str]:
    """Return the problems with a snap request, without raising.

    The result is a list of exact strings, at most one of each kind and in this
    order:

    * ``"negative size"`` when ``rect["w"] < 0`` or ``rect["h"] < 0``.
    * ``"threshold out of range"`` when ``threshold`` is outside
      ``[MIN_THRESHOLD, MAX_THRESHOLD]`` in px (inclusive bounds).
    * ``"reference is self"`` when any entry of *others* is the same object as
      *rect* or has all four geometry fields equal within ``PIXEL_TOLERANCE``
      (0.5 px).

    An empty list means the request is valid. A bad threshold is reported here
    as an issue; :func:`snap_offset` is the function that raises
    :class:`SnapError` for it.
    """
    problems: list[str] = []

    try:
        negative = rect["w"] < 0 or rect["h"] < 0
    except (KeyError, TypeError):
        negative = False
    if negative:
        problems.append("negative size")

    if not _valid_threshold(threshold):
        problems.append("threshold out of range")

    if any(_is_self(other, rect) for other in others):
        problems.append("reference is self")

    return problems


def snap_batch(events: list[dict], config: dict) -> dict:
    """Snap a sequence of independent events atomically.

    ``events`` is a list of dictionaries with a rectangle under ``"rect"`` and
    reference rectangles under ``"others"``. ``config`` must provide the snap
    distance in px under ``"threshold"``. Each event must use only its own
    references; guide lines accumulated for one event may never leak into the
    next event. The input order is preserved in the output.

    On success return::

        {
            "ok": True,
            "results": [
                {"rect": <snapped rect>, "offset": {"dx", "dy", "hit"},
                 "guides": [<that event's candidates>]},
                ...
            ],
            "error": None,
        }

    If any event is invalid (negative size, threshold out of range, a self
    reference, or malformed input), nothing is applied. Return
    ``{"ok": False, "results": [], "error": "<non-empty message>"}`` as a
    single all-or-nothing rollback instead of a partial result. All offsets and
    guide values are in px.
    """
    try:
        threshold = config["threshold"]
    except (KeyError, TypeError):
        return {"ok": False, "results": [], "error": "missing threshold"}

    if not _valid_threshold(threshold):
        return {
            "ok": False,
            "results": [],
            "error": "threshold out of range",
        }

    results = []
    for event in events:
        try:
            rect = event["rect"]
            others = event.get("others", [])
            for key in _GEOMETRY_KEYS:
                rect[key]
            if not isinstance(others, (list, tuple)):
                raise TypeError("others must be a sequence")
            for other in others:
                for key in _GEOMETRY_KEYS:
                    other[key]
        except (KeyError, TypeError):
            return {
                "ok": False,
                "results": [],
                "error": "malformed event",
            }

        problems = validate(rect, others, threshold)
        if problems:
            return {
                "ok": False,
                "results": [],
                "error": "; ".join(problems),
            }

        candidates = guide_candidates(others, rect)
        offset = snap_offset(rect, candidates, threshold)
        results.append(
            {
                "rect": apply_snap(rect, offset),
                "offset": offset,
                "guides": candidates,
            }
        )

    return {"ok": True, "results": results, "error": None}
