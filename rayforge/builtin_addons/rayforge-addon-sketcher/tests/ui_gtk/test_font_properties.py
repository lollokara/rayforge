import os
import sys
from pathlib import Path
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
from sketcher.core import Sketch, fonts, text_presets
from sketcher.ui_gtk.font_properties import (
    FontPropertiesWidget,
    split_text_selection,
)

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


@pytest.mark.ui
def test_split_text_selection(widget_with_box):
    _, sketch, tb_id = widget_with_box
    registry = sketch.registry
    p1 = sketch.add_point(0, 50)
    p2 = sketch.add_point(100, 50)
    line_id = sketch.add_line(p1, p2)
    other_line = sketch.add_line(p2, sketch.add_point(100, 90))

    assert split_text_selection(registry, [tb_id]) == (tb_id, None)
    assert split_text_selection(registry, [line_id, tb_id]) == (
        tb_id,
        line_id,
    )
    assert split_text_selection(registry, [line_id]) == (None, None)
    assert split_text_selection(registry, [tb_id, line_id, other_line]) == (
        None,
        None,
    )
    assert split_text_selection(registry, []) == (None, None)


@pytest.mark.ui
def test_follow_path_binds_and_releases(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)
    line_id = sketch.add_line(
        sketch.add_point(0, 50), sketch.add_point(100, 50)
    )

    widget.set_text_entity(tb_id, line_id)
    widget._on_follow_path_activated(widget.follow_path_row)
    assert entity.path_entity_id == line_id

    widget.set_text_entity(tb_id)
    widget._on_follow_path_activated(widget.follow_path_row)
    assert entity.path_entity_id is None


@pytest.mark.ui
def test_path_rows_apply_style(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)

    widget.path_side_row.set_selected(1)
    widget.path_align_row.set_selected(0)
    widget.path_offset_row.set_value_in_base_units(2.5)
    widget.bottom_text_row.set_text("BOTTOM")
    widget._on_style_changed()

    assert entity.path_side == "inside"
    assert entity.path_align == "start"
    assert entity.path_offset == pytest.approx(2.5)
    assert entity.content_bottom == "BOTTOM"


FONT_FILE = Path(__file__).parents[1] / "assets" / "TestFont-Regular.ttf"


@pytest.fixture
def font_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    monkeypatch.setattr(fonts, "_families_by_file", {})
    return tmp_path


@pytest.mark.ui
def test_install_font_selects_it(font_data_dir, widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)

    widget._install_font_file(FONT_FILE)

    family = fonts.list_custom_families()[0]
    assert entity.font_config.family == family
    assert widget.missing_font_row.get_visible() is False


@pytest.mark.ui
def test_missing_font_shows_warning(font_data_dir, widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)
    entity.font_config = FontConfig(family="Totally Missing Font", size=10.0)

    widget.set_text_entity(tb_id)

    assert widget.missing_font_row.get_visible() is True


@pytest.mark.ui
def test_install_rejected_file_keeps_font(font_data_dir, widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)
    before = entity.font_config.family
    bogus = font_data_dir / "broken.ttf"
    bogus.write_bytes(b"not a font")

    widget._install_font_file(bogus)

    assert entity.font_config.family == before


@pytest.fixture
def preset_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    return tmp_path


@pytest.mark.ui
def test_save_preset_from_current_text(preset_data_dir, widget_with_box):
    widget, sketch, tb_id = widget_with_box
    sketch.registry.get_entity(tb_id).set_style({"mirrored": True})
    widget.set_text_entity(tb_id)

    widget.save_preset_row.set_text("Mirrored")
    widget._on_save_preset_applied(widget.save_preset_row)

    (preset,) = text_presets.load_presets()
    assert preset.name == "Mirrored"
    assert preset.style["mirrored"] is True
    assert widget.save_preset_row.get_text() == ""


@pytest.mark.ui
def test_apply_preset_is_one_undo_step(preset_data_dir, widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)
    preset = text_presets.TextPreset(
        "Big",
        FontConfig(family="serif", size=20.0).to_dict(),
        {"vertical": True, "rotation": 90.0},
    )

    widget._apply_preset(preset)

    assert entity.font_config.size == 20.0
    assert entity.vertical is True
    assert entity.content == "Hello"
    assert widget.vertical_switch.get_active() is True

    widget.editor.history_manager.undo()
    assert entity.font_config.size == 10.0
    assert entity.vertical is False


@pytest.mark.ui
def test_delete_selected_preset(preset_data_dir, widget_with_box):
    widget, _, tb_id = widget_with_box
    text_presets.save_preset(
        text_presets.TextPreset("Gone", FontConfig().to_dict(), {})
    )
    widget.set_text_entity(tb_id)
    widget.preset_row.set_selected(1)

    widget._on_delete_preset_activated(widget.delete_preset_row)

    assert text_presets.load_presets() == []


@pytest.mark.ui
def test_blank_preset_name_is_not_saved(preset_data_dir, widget_with_box):
    widget, _, _ = widget_with_box
    widget.save_preset_row.set_text("   ")
    widget._on_save_preset_applied(widget.save_preset_row)
    assert text_presets.load_presets() == []


@pytest.mark.ui
def test_insert_serial_appends_template(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)

    widget._on_insert_serial_activated(widget.insert_serial_row)

    assert entity.content == "Hello{serial()}"

    widget.editor.history_manager.undo()
    assert entity.content == "Hello"


@pytest.mark.ui
def test_insert_serial_subtitle_explains_then_shows_next_number(
    widget_with_box, tmp_path, monkeypatch
):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    widget, _sketch, _tb_id = widget_with_box
    hint = widget.insert_serial_row.get_subtitle() or ""

    assert "{serial()}" in hint
    assert "Settings" in hint

    widget._on_insert_serial_activated(widget.insert_serial_row)

    subtitle = widget.insert_serial_row.get_subtitle() or ""
    assert subtitle.startswith("Next number: 1.")


@pytest.mark.ui
def test_insert_serial_subtitle_lists_named_counters(
    widget_with_box, tmp_path, monkeypatch
):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)
    entity.content = 'A{serial("batch")} B{serial("lot")}'

    widget.set_text_entity(tb_id)

    subtitle = widget.insert_serial_row.get_subtitle() or ""
    assert "batch: 1" in subtitle
    assert "lot: 1" in subtitle
