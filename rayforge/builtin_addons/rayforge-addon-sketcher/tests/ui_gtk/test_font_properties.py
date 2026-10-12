import os
import sys
from unittest.mock import Mock

import pytest

if sys.platform.startswith("linux"):
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    if not os.environ.get("DISPLAY"):
        pytest.skip(
            "DISPLAY not set on Linux, skipping UI tests. Run with xvfb-run.",
            allow_module_level=True,
        )

from raygeo.geo.shape.text import FontConfig
from sketcher.core import Sketch
from sketcher.ui_gtk.font_properties import FontPropertiesWidget

from rayforge.core.undo import HistoryManager


@pytest.fixture
def widget_with_box():
    """A FontPropertiesWidget showing one text box of a real sketch."""
    sketch = Sketch()
    p_origin = sketch.add_point(0, 0)
    p_width = sketch.add_point(50, 0)
    p_height = sketch.add_point(0, 10)
    tb_id = sketch.registry.add_text_box(
        p_origin, p_width, p_height, content="Hello", font_config=FontConfig()
    )
    editor = Mock()
    editor.sketch_element.sketch = sketch
    editor.sketch_element.tools.get.return_value = None
    editor.history_manager = HistoryManager()
    widget = FontPropertiesWidget(editor)
    widget.set_text_entity(tb_id)
    return widget, sketch, tb_id


@pytest.mark.ui
def test_transform_rows_apply_style(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)

    widget.mirror_switch.set_active(True)
    widget.rotation_row.set_value(90.0)
    widget.rotation_row.value_changed.send(widget.rotation_row)

    assert entity.mirrored is True
    assert entity.rotation == 90.0

    widget.editor.history_manager.undo()
    assert entity.rotation == 0.0
    assert entity.mirrored is True

    widget.editor.history_manager.undo()
    assert entity.rotation == 0.0
    assert entity.mirrored is False


@pytest.mark.ui
def test_upside_down_sets_rotation_180(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)

    widget._on_upside_down_changed(widget.upside_down_switch, True)

    assert entity.rotation == 180.0


@pytest.mark.ui
def test_widget_shows_entity_style(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)
    entity.set_style({"vertical": True, "rotation": 180.0})

    widget.set_text_entity(tb_id)

    assert widget.vertical_switch.get_active() is True
    assert widget.upside_down_switch.get_active() is True
    assert widget.rotation_row.get_value() == 180.0


@pytest.mark.ui
def test_knockout_rows_apply_style(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)

    widget.knockout_switch.set_active(True)
    widget.knockout_margin_row.set_value_in_base_units(3.0)
    widget._on_style_changed()

    assert entity.knockout is True
    assert entity.knockout_margin == pytest.approx(3.0)


@pytest.mark.ui
def test_widget_shows_knockout_style(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    sketch.registry.get_entity(tb_id).set_style(
        {"knockout": True, "knockout_margin": 4.0}
    )

    widget.set_text_entity(tb_id)

    assert widget.knockout_switch.get_active() is True
    assert widget.knockout_margin_row.get_value_in_base_units() == (
        pytest.approx(4.0)
    )
