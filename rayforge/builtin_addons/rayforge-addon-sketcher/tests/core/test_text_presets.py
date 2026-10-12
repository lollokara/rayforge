import json

import pytest
from raygeo.geo.shape.text import FontConfig
from sketcher.core import text_presets
from sketcher.core.entities import TextBoxEntity
from sketcher.core.text_presets import (
    TextPreset,
    delete_preset,
    load_presets,
    preset_from_entity,
    save_preset,
)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    return tmp_path


def _styled_box():
    box = TextBoxEntity(
        1, 2, 3, 4, "CONTENT", FontConfig(family="serif", size=14.0, bold=True)
    )
    box.set_style(
        {
            "mirrored": True,
            "rotation": 90.0,
            "knockout": True,
            "knockout_margin": 3.0,
            "path_entity_id": 9,
            "path_side": "inside",
            "content_bottom": "BOTTOM",
        }
    )
    return box


def test_no_file_means_no_presets():
    assert load_presets() == []


def test_preset_round_trip():
    save_preset(preset_from_entity("Label", _styled_box()))

    (preset,) = load_presets()

    assert preset.name == "Label"
    assert preset.font_config() == FontConfig(
        family="serif", size=14.0, bold=True
    )
    assert preset.style["mirrored"] is True
    assert preset.style["rotation"] == 90.0
    assert preset.style["path_side"] == "inside"


def test_preset_has_no_content_or_path_binding():
    preset = preset_from_entity("Label", _styled_box())
    assert "path_entity_id" not in preset.style
    assert "content_bottom" not in preset.style
    assert "CONTENT" not in json.dumps([preset.font, preset.style])


def test_applying_a_preset_sets_every_style_field():
    preset = preset_from_entity("Label", _styled_box())
    target = TextBoxEntity(5, 6, 7, 8, "KEEP ME")
    target.set_style({"path_entity_id": 3, "content_bottom": "KEEP"})

    target.set_style(preset.style)

    for key in text_presets.PRESET_STYLE_KEYS:
        assert getattr(target, key) == getattr(_styled_box(), key)
    assert target.path_entity_id == 3
    assert target.content_bottom == "KEEP"
    assert target.content == "KEEP ME"


def test_save_replaces_preset_of_same_name():
    save_preset(TextPreset("A", FontConfig(size=5.0).to_dict(), {}))
    save_preset(TextPreset("A", FontConfig(size=9.0).to_dict(), {}))
    (preset,) = load_presets()
    assert preset.font_config().size == 9.0


def test_presets_are_sorted_by_name():
    save_preset(TextPreset("Zeta", FontConfig().to_dict(), {}))
    save_preset(TextPreset("alpha", FontConfig().to_dict(), {}))
    assert [p.name for p in load_presets()] == ["alpha", "Zeta"]


def test_delete_preset():
    save_preset(TextPreset("A", FontConfig().to_dict(), {}))
    delete_preset("A")
    delete_preset("missing")
    assert load_presets() == []


def test_corrupt_file_returns_empty_list():
    text_presets.presets_path().write_text("{ not json", encoding="utf-8")
    assert load_presets() == []


def test_unknown_keys_and_bad_entries_are_ignored():
    text_presets.presets_path().write_text(
        json.dumps(
            {
                "presets": [
                    {
                        "name": "Good",
                        "font": FontConfig().to_dict(),
                        "style": {"mirrored": True, "bogus": 1},
                        "future": "field",
                    },
                    {"font": {}},
                    "garbage",
                ]
            }
        ),
        encoding="utf-8",
    )
    (preset,) = load_presets()
    assert preset.name == "Good"
    assert preset.style == {"mirrored": True}


def test_save_leaves_no_temp_file(data_dir):
    save_preset(TextPreset("A", FontConfig().to_dict(), {}))
    assert [p.name for p in (data_dir / "sketcher").iterdir()] == [
        "text_presets.json"
    ]
