"""Lays text out along a polyline, one glyph at a time.

raygeo lays text out character by character without kerning or
shaping, so placing each character's outline at its advance position
on the path reproduces the straight layout exactly on a straight path.
"""

from __future__ import annotations

import math

from raygeo.geo import Geometry, Matrix
from raygeo.geo.shape.text import FontConfig, text_to_geometry

from .polyline import cumulative_lengths, point_at_arclength

Polyline = list[tuple[float, float]]


def _is_closed(polyline: Polyline) -> bool:
    (x0, y0), (x1, y1) = polyline[0], polyline[-1]
    return math.hypot(x1 - x0, y1 - y0) < 1e-6


def _start_position(
    align: str, total: float, width: float, offset: float
) -> float:
    if align == "start":
        return offset
    if align == "end":
        return total - width + offset
    return (total - width) / 2.0 + offset


def _locate(
    polyline: Polyline, cum: list[float], s: float, closed: bool
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Point and unit tangent at arc length ``s``. Closed paths wrap;
    open paths continue along their end tangent."""
    total = cum[-1]
    if closed:
        return point_at_arclength(polyline, cum, s % total)
    point, tangent = point_at_arclength(polyline, cum, s)
    overshoot = s - total if s > total else min(s, 0.0)
    return (
        (
            point[0] + tangent[0] * overshoot,
            point[1] + tangent[1] * overshoot,
        ),
        tangent,
    )


def _inside_polyline(polyline: Polyline) -> Polyline:
    """
    Reverses *polyline* for inside text. A closed path is also rolled by
    half its points, so the centre of the reversed path lies on the side
    of the circle opposite the centre of the original path.
    """
    reversed_line = polyline[::-1]
    if not _is_closed(reversed_line):
        return reversed_line
    ring = reversed_line[:-1]
    half = len(ring) // 2
    rolled = ring[half:] + ring[:half]
    return rolled + [rolled[0]]


def text_on_path(
    text: str,
    font_config: FontConfig,
    polyline: Polyline,
    side: str = "outside",
    align: str = "center",
    offset: float = 0.0,
) -> Geometry:
    """
    Returns the glyph outlines of *text* laid along *polyline*.

    Each character sits at its advance position measured as arc
    length, rotated to the path tangent. "outside" places the glyphs
    on the left of the travel direction; "inside" reverses the path,
    which flips both the normal and the reading direction.
    """
    geo = Geometry()
    if len(polyline) < 2:
        return geo
    if side == "inside":
        polyline = _inside_polyline(polyline)
    cum = cumulative_lengths(polyline)
    total = cum[-1]
    if total <= 1e-9:
        return geo

    closed = _is_closed(polyline)
    start = _start_position(
        align, total, font_config.get_text_width(text), offset
    )
    for index, char in enumerate(text):
        glyph = text_to_geometry(char, font_config=font_config)
        if glyph.is_empty():
            continue
        advance = font_config.get_text_width(char)
        s = start + font_config.get_text_position(text, index) + advance / 2
        (px, py), (tx, ty) = _locate(polyline, cum, s, closed)
        glyph.transform(
            Matrix.translation(px, py)
            @ Matrix.rotation(math.degrees(math.atan2(ty, tx)))
            @ Matrix.translation(-advance / 2.0, 0.0)
        )
        geo.extend(glyph)
    return geo
