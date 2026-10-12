"""Arc-length helpers for polylines given as lists of (x, y) points."""

from __future__ import annotations

import math


def cumulative_lengths(
    polyline: list[tuple[float, float]],
) -> list[float]:
    cum = [0.0]
    for i in range(1, len(polyline)):
        dx = polyline[i][0] - polyline[i - 1][0]
        dy = polyline[i][1] - polyline[i - 1][1]
        cum.append(cum[-1] + math.hypot(dx, dy))
    return cum


def point_at_arclength(
    polyline: list[tuple[float, float]],
    cum: list[float],
    s: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Returns (point, unit_tangent) at arc length ``s`` along the path."""
    if s <= 0.0:
        dx = polyline[1][0] - polyline[0][0]
        dy = polyline[1][1] - polyline[0][1]
        n = math.hypot(dx, dy) or 1.0
        return polyline[0], (dx / n, dy / n)
    if s >= cum[-1]:
        a = polyline[-2]
        b = polyline[-1]
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        return b, (dx / n, dy / n)

    # Binary search for the segment containing s.
    lo, hi = 0, len(cum) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cum[mid] < s:
            lo = mid + 1
        else:
            hi = mid
    seg = max(1, lo)
    a = polyline[seg - 1]
    b = polyline[seg]
    seg_len = cum[seg] - cum[seg - 1]
    t = (s - cum[seg - 1]) / seg_len if seg_len > 0 else 0.0
    point = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    return point, (dx / n, dy / n)
