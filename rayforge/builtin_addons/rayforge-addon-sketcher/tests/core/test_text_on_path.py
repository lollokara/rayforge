import math

import pytest
from raygeo.geo.shape.text import FontConfig, text_to_geometry
from sketcher.core.text_on_path import text_on_path

FONT = FontConfig(family="sans-serif", size=10.0)
RADIUS = 50.0


def _clockwise_circle_from_bottom(radius=RADIUS, segments=96):
    """Closed circle about the origin, clockwise, starting at the
    bottom, so the middle of the path is the top."""
    return [
        (
            radius * math.cos(-math.pi / 2 - 2 * math.pi * i / segments),
            radius * math.sin(-math.pi / 2 - 2 * math.pi * i / segments),
        )
        for i in range(segments + 1)
    ]


def _radii(geo):
    return [
        math.hypot(x, y) for ring in geo.to_polygons(0.01) for x, y in ring
    ]


def test_ring_count_is_preserved():
    line = [(0.0, 0.0), (200.0, 0.0)]
    on_path = text_on_path("HELLO", FONT, line, align="start")
    plain = text_to_geometry("HELLO", font_config=FONT)
    assert len(on_path.to_polygons(0.01)) == len(plain.to_polygons(0.01))


def test_start_aligned_text_on_x_axis_matches_plain_layout():
    line = [(0.0, 0.0), (200.0, 0.0)]
    on_path = text_on_path("HELLO", FONT, line, align="start")
    plain = text_to_geometry("HELLO", font_config=FONT)
    assert on_path.rect() == pytest.approx(plain.rect(), abs=1e-3)


def test_outside_text_stays_outside_circle():
    geo = text_on_path("HHHHHHHHHH", FONT, _clockwise_circle_from_bottom())
    radii = _radii(geo)
    assert min(radii) >= RADIUS - 0.2
    assert max(radii) > RADIUS + 1.0


def test_inside_text_stays_inside_circle():
    geo = text_on_path(
        "HHHHHHHHHH", FONT, _clockwise_circle_from_bottom(), side="inside"
    )
    radii = _radii(geo)
    assert max(radii) <= RADIUS + 0.2
    assert min(radii) < RADIUS - 1.0


def test_centre_aligned_text_sits_at_top_of_circle():
    geo = text_on_path("HHHH", FONT, _clockwise_circle_from_bottom())
    min_x, min_y, max_x, _ = geo.rect()
    assert (min_x + max_x) / 2 == pytest.approx(0.0, abs=0.5)
    assert min_y > 0.0


def test_inside_centre_aligned_text_sits_at_bottom_of_circle():
    geo = text_on_path("HHHH", FONT, _clockwise_circle_from_bottom(), "inside")
    _, _, _, max_y = geo.rect()
    assert max_y < 0.0


def test_end_alignment_ends_at_path_end():
    line = [(0.0, 0.0), (200.0, 0.0)]
    geo = text_on_path("HELLO", FONT, line, align="end")
    width = FONT.get_text_width("HELLO")
    assert geo.rect()[0] >= 200.0 - width - 0.01
    assert geo.rect()[2] <= 200.0 + 0.01


def test_offset_shifts_along_path():
    line = [(0.0, 0.0), (200.0, 0.0)]
    base = text_on_path("HI", FONT, line, align="start")
    shifted = text_on_path("HI", FONT, line, align="start", offset=7.0)
    assert shifted.rect()[0] == pytest.approx(base.rect()[0] + 7.0)


def test_text_longer_than_open_path_extends_along_tangent():
    short = [(0.0, 0.0), (5.0, 0.0)]
    geo = text_on_path("HELLO WORLD", FONT, short, align="start")
    plain = text_to_geometry("HELLO WORLD", font_config=FONT)
    assert geo.rect() == pytest.approx(plain.rect(), abs=1e-3)


def test_blank_text_on_path_is_empty():
    line = [(0.0, 0.0), (10.0, 0.0)]
    assert text_on_path("   ", FONT, line).is_empty()
    assert text_on_path("", FONT, line).is_empty()


def test_degenerate_polyline_is_empty():
    assert text_on_path("HI", FONT, [(1.0, 1.0)]).is_empty()
    assert text_on_path("HI", FONT, [(1.0, 1.0), (1.0, 1.0)]).is_empty()
