from unittest.mock import Mock

import pytest
from raygeo.geo import Geometry
from raygeo.geo.shape.text import FontConfig
from sketcher.core.entities import TextBoxEntity
from sketcher.core.entities.text_box import STYLE_DEFAULTS
from sketcher.core.registry import EntityRegistry


@pytest.fixture
def registry():
    return EntityRegistry()


def test_text_box_serialization_round_trip():
    """Tests to_dict and from_dict methods for a single TextBox."""
    original_box = TextBoxEntity(
        id=10,
        origin_id=1,
        width_id=2,
        height_id=3,
        content="Hello World",
        font_config=FontConfig(
            family="sans-serif",
            size=10.0,
            bold=False,
            italic=False,
        ),
    )

    data = original_box.to_dict()
    assert data["id"] == 10
    assert data["type"] == "text_box"
    assert data["origin_id"] == 1
    assert data["width_id"] == 2
    assert data["height_id"] == 3
    assert data["content"] == "Hello World"
    assert data["font_config"] == {
        "font_family": "sans-serif",
        "font_size": 10.0,
        "bold": False,
        "italic": False,
    }

    new_box = TextBoxEntity.from_dict(data)
    assert isinstance(new_box, TextBoxEntity)
    assert new_box.id == original_box.id
    assert new_box.origin_id == original_box.origin_id
    assert new_box.width_id == original_box.width_id
    assert new_box.height_id == original_box.height_id
    assert new_box.content == original_box.content
    assert new_box.font_config == original_box.font_config


def test_text_box_get_point_ids(registry):
    """Tests that a text box correctly reports its defining point IDs."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, "Test", FontConfig())
    )
    assert set(box.get_point_ids()) == {p1, p2, p3}


def test_text_box_get_endpoint_ids(registry):
    """Tests that a text box has no endpoints (not a path entity)."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, "Test", FontConfig())
    )
    assert box.get_endpoint_ids() == []


def test_text_box_get_junction_point_ids(registry):
    """Tests that a text box has no junction point IDs."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, "Test", FontConfig())
    )
    assert box.get_junction_point_ids() == []


def test_text_box_hit_test(registry):
    """Tests TextBoxEntity.hit_test method."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, "Test", FontConfig())
    )
    threshold = 5.0

    # Point inside the text box
    assert box.hit_test(2, 2, threshold, registry) is True
    assert box.hit_test(5, 5, threshold, registry) is True

    # Point outside the text box
    assert box.hit_test(15, 5, threshold, registry) is False
    assert box.hit_test(5, 15, threshold, registry) is False
    assert box.hit_test(-5, 5, threshold, registry) is False


def test_text_box_get_all_frame_point_ids(registry):
    """Tests that a text box correctly reports all frame point IDs."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, "Test", FontConfig())
    )

    assert set(box.get_all_frame_point_ids(registry)) == {p1, p2, p3}

    p4 = registry.add_point(10, 10)
    line_id = registry.add_line(p2, p4, construction=True)
    box.construction_line_ids = [line_id]

    assert set(box.get_all_frame_point_ids(registry)) == {p1, p2, p3, p4}


def test_text_box_update_constrained_status(registry):
    """Test TextBoxEntity.update_constrained_status logic."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, "Test", FontConfig())
    )

    pt1 = registry.get_point(p1)
    pt2 = registry.get_point(p2)
    pt3 = registry.get_point(p3)

    # Initially unconstrained
    pt1.constrained = False
    pt2.constrained = False
    pt3.constrained = False
    box.update_constrained_status(registry, [])
    assert box.constrained is False

    # One point constrained
    pt1.constrained = True
    box.update_constrained_status(registry, [])
    assert box.constrained is False

    # Two points constrained
    pt2.constrained = True
    box.update_constrained_status(registry, [])
    assert box.constrained is False

    # All three points constrained
    pt3.constrained = True
    box.update_constrained_status(registry, [])
    assert box.constrained is True


@pytest.fixture
def selection_setup(registry):
    """Fixture for setting up text box entities for selection tests."""
    rect = (20, 20, 80, 80)

    # Text box fully inside
    p_in1 = registry.add_point(30, 30)
    p_in2 = registry.add_point(70, 30)
    p_in3 = registry.add_point(30, 70)
    box_in = registry.get_entity(
        registry.add_text_box(p_in1, p_in2, p_in3, "Inside", {})
    )

    # Text box intersecting
    p_cross1 = registry.add_point(10, 50)
    p_cross2 = registry.add_point(90, 50)
    p_cross3 = registry.add_point(10, 90)
    box_cross = registry.get_entity(
        registry.add_text_box(p_cross1, p_cross2, p_cross3, "Crossing", {})
    )

    # Text box outside
    p_out1 = registry.add_point(0, 0)
    p_out2 = registry.add_point(10, 0)
    p_out3 = registry.add_point(0, 10)
    box_out = registry.get_entity(
        registry.add_text_box(p_out1, p_out2, p_out3, "Outside", {})
    )

    return (
        registry,
        rect,
        {
            "box_in": box_in,
            "box_cross": box_cross,
            "box_out": box_out,
        },
    )


def test_text_box_is_contained_by(selection_setup):
    """Test is_contained_by method for TextBox entities."""
    registry, rect, entities = selection_setup
    assert entities["box_in"].is_contained_by(rect, registry) is True
    assert entities["box_cross"].is_contained_by(rect, registry) is False
    assert entities["box_out"].is_contained_by(rect, registry) is False


def test_text_box_intersects_rect(selection_setup):
    """Test of intersects_rect method for TextBox entities."""
    registry, rect, entities = selection_setup
    assert entities["box_in"].intersects_rect(rect, registry) is True
    assert entities["box_cross"].intersects_rect(rect, registry) is True
    assert entities["box_out"].intersects_rect(rect, registry) is False


def test_text_box_to_geometry(registry):
    """Test TextBoxEntity.to_geometry method."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, "Test", FontConfig())
    )
    geo = box.to_geometry(registry)
    assert isinstance(geo, Geometry)
    assert len(geo) > 0


def test_text_box_get_set_state(registry):
    """Test state capture and restoration for Undo/Redo."""
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    tb = registry.get_entity(registry.add_text_box(p1, p2, p3, "Test", {}))

    # Verify initial state (Inherited from Entity)
    state = tb.get_state()
    assert state == {"construction": False, "fill_color": None}

    # Modify state
    tb.construction = True

    # Restore state
    tb.set_state(state)
    assert tb.construction is False


def test_text_box_get_fourth_corner_id(registry):
    """Tests finding the fourth corner of a text box frame."""
    origin = registry.add_point(0, 0)
    width = registry.add_point(100, 0)
    height = registry.add_point(0, 50)
    p4 = registry.add_point(100, 50)

    line2 = registry.add_line(width, p4)

    box = TextBoxEntity(
        id=100,
        origin_id=origin,
        width_id=width,
        height_id=height,
        content="Test",
        construction_line_ids=[line2],
    )
    registry.entities.append(box)

    result = box.get_fourth_corner_id(registry)

    assert result == p4


def test_text_box_get_fourth_corner_id_from_reverse_line(registry):
    """Tests finding fourth corner from a line going the other direction."""
    origin = registry.add_point(0, 0)
    width = registry.add_point(100, 0)
    height = registry.add_point(0, 50)
    p4 = registry.add_point(100, 50)

    line2 = registry.add_line(p4, width)

    box = TextBoxEntity(
        id=100,
        origin_id=origin,
        width_id=width,
        height_id=height,
        content="Test",
        construction_line_ids=[line2],
    )
    registry.entities.append(box)

    result = box.get_fourth_corner_id(registry)

    assert result == p4


def test_text_box_get_fourth_corner_id_no_construction_lines(registry):
    """Tests that None is returned when no construction lines exist."""
    origin = registry.add_point(0, 0)
    width = registry.add_point(100, 0)
    height = registry.add_point(0, 50)

    box = TextBoxEntity(
        id=100,
        origin_id=origin,
        width_id=width,
        height_id=height,
        content="Test",
        construction_line_ids=[],
    )
    registry.entities.append(box)

    result = box.get_fourth_corner_id(registry)

    assert result is None


def test_text_box_get_fourth_corner_id_wrong_line(registry):
    """Tests that None is returned when no line connects to width point."""
    origin = registry.add_point(0, 0)
    width = registry.add_point(100, 0)
    height = registry.add_point(0, 50)
    other = registry.add_point(200, 200)

    wrong_line = registry.add_line(origin, other)

    box = TextBoxEntity(
        id=100,
        origin_id=origin,
        width_id=width,
        height_id=height,
        content="Test",
        construction_line_ids=[wrong_line],
    )
    registry.entities.append(box)

    result = box.get_fourth_corner_id(registry)

    assert result is None


def test_text_box_get_fourth_corner_id_ignores_origin_and_height(registry):
    """Tests that lines to origin or height are ignored."""
    origin = registry.add_point(0, 0)
    width = registry.add_point(100, 0)
    height = registry.add_point(0, 50)

    line_to_origin = registry.add_line(width, origin)
    line_to_height = registry.add_line(width, height)

    box = TextBoxEntity(
        id=100,
        origin_id=origin,
        width_id=width,
        height_id=height,
        content="Test",
        construction_line_ids=[line_to_origin, line_to_height],
    )
    registry.entities.append(box)

    result = box.get_fourth_corner_id(registry)

    assert result is None


def _make_text_box(registry, content="Hello"):
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box_id = registry.add_text_box(p1, p2, p3, content, FontConfig())
    return registry.get_entity(box_id)


def test_serialization_preserves_template(registry):
    """Template content is preserved through serialization."""
    box = _make_text_box(registry, "Part {width:.1f}x{height:.1f}")
    data = box.to_dict()
    assert data["content"] == "Part {width:.1f}x{height:.1f}"

    restored = TextBoxEntity.from_dict(data)
    assert restored.content == "Part {width:.1f}x{height:.1f}"


_NON_DEFAULT_STYLE = {
    "mirrored": True,
    "reverse": True,
    "vertical": True,
    "rotation": 90.0,
    "knockout": True,
    "knockout_margin": 3.5,
    "path_entity_id": 42,
    "path_side": "inside",
    "path_align": "start",
    "path_offset": 1.5,
    "content_bottom": "BOTTOM",
}


def test_style_defaults():
    box = TextBoxEntity(1, 2, 3, 4, "x")
    assert box.get_style() == STYLE_DEFAULTS


def test_style_defaults_are_not_serialized():
    data = TextBoxEntity(1, 2, 3, 4, "x").to_dict()
    assert not set(STYLE_DEFAULTS) & set(data)


def test_style_round_trip():
    box = TextBoxEntity(1, 2, 3, 4, "x")
    box.set_style(_NON_DEFAULT_STYLE)
    restored = TextBoxEntity.from_dict(box.to_dict())
    assert restored.get_style() == _NON_DEFAULT_STYLE


def test_from_dict_without_style_keys_loads_defaults():
    data = {
        "id": 1,
        "type": "text_box",
        "origin_id": 2,
        "width_id": 3,
        "height_id": 4,
        "content": "legacy",
    }
    assert TextBoxEntity.from_dict(data).get_style() == STYLE_DEFAULTS


def test_from_dict_ignores_invalid_style_values():
    data = TextBoxEntity(1, 2, 3, 4, "x").to_dict()
    data.update(
        {
            "rotation": "abc",
            "mirrored": 1,
            "path_side": "sideways",
            "path_entity_id": "7",
            "knockout_margin": float("nan"),
            "content_bottom": 5,
        }
    )
    assert TextBoxEntity.from_dict(data).get_style() == STYLE_DEFAULTS


def test_set_style_coerces_int_to_float():
    box = TextBoxEntity(1, 2, 3, 4, "x")
    box.set_style({"rotation": 180})
    assert box.rotation == 180.0
    assert isinstance(box.rotation, float)


def test_style_changes_geometry_signature(registry):
    box = _make_text_box(registry)
    before = box.geometry_signature(registry)
    box.mirrored = True
    assert box.geometry_signature(registry) != before


def test_rewrite_offsets_copies_style(registry):
    template = _make_text_box(registry)
    template.set_style({"mirrored": True, "rotation": 45.0})
    copy_box = _make_text_box(registry, "Other")
    copy_box.rewrite_offsets_from(template, Mock())
    assert copy_box.get_style() == template.get_style()
