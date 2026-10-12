import pytest
from raygeo.geo.shape.text import FontConfig
from sketcher.core import Sketch
from sketcher.core.entities.text_box import TextBoxEntity
from sketcher.core.serial import load_counters
from sketcher.core.serial_dispatch import (
    on_job_dispatched,
    refresh_current_doc,
    refresh_serials,
    serial_names_in_sketch,
    serial_workpieces,
    set_doc_source,
)

from rayforge.core.doc import Doc
from rayforge.core.workpiece import WorkPiece


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    return tmp_path


def _sketch_with_text(content, bottom=""):
    sketch = Sketch()
    origin = sketch.add_point(0, 0)
    width_pt = sketch.add_point(10, 0)
    height_pt = sketch.add_point(0, 10)
    box = sketch.registry.get_entity(
        sketch.registry.add_text_box(
            origin, width_pt, height_pt, content, FontConfig()
        )
    )
    assert isinstance(box, TextBoxEntity)
    box.content_bottom = bottom
    sketch.solve()
    return sketch


def _add_workpiece(doc, sketch):
    doc.add_asset(sketch)
    wp = WorkPiece.from_geometry_provider(sketch)
    wp.geometry_provider_uid = sketch.uid
    doc.active_layer.add_child(wp)
    return wp


def _resolved(wp):
    return [resolved for _source, resolved in wp._resolved_text_cache.values()]


def test_serial_names_in_sketch():
    sketch = _sketch_with_text('{serial("a")} {serial()}', '{serial("b")}')
    assert serial_names_in_sketch(sketch) == {"a", "b", "default"}


def test_sketch_without_serials_has_no_names():
    assert serial_names_in_sketch(_sketch_with_text("plain")) == set()


def test_serial_workpieces_lists_only_serial_users():
    doc = Doc()
    plain = _add_workpiece(doc, _sketch_with_text("plain"))
    numbered = _add_workpiece(doc, _sketch_with_text("{serial()}"))

    found = serial_workpieces(doc)

    assert [wp for wp, _names in found] == [numbered]
    assert plain not in [wp for wp, _names in found]


def test_dispatch_advances_each_counter_once():
    doc = Doc()
    shared = _sketch_with_text('{serial("a")}')
    _add_workpiece(doc, shared)
    _add_workpiece(doc, _sketch_with_text('{serial("a")} {serial("b")}'))

    on_job_dispatched(doc)

    counters = load_counters()
    assert counters["a"].value == 2
    assert counters["b"].value == 2


def test_dispatch_refreshes_the_workpiece_text():
    doc = Doc()
    wp = _add_workpiece(doc, _sketch_with_text("{serial()}"))
    wp.regenerate_from_geometry_provider()
    assert _resolved(wp) == ["1"]

    on_job_dispatched(doc)

    assert _resolved(wp) == ["2"]


def test_dispatch_without_serials_writes_nothing(data_dir):
    doc = Doc()
    _add_workpiece(doc, _sketch_with_text("plain"))

    on_job_dispatched(doc)

    assert not (data_dir / "sketcher" / "serials.json").exists()


def test_refresh_replaces_stale_cached_serial():
    """A project saved with an already engraved number must show the
    current counter value after loading."""
    doc = Doc()
    wp = _add_workpiece(doc, _sketch_with_text("{serial()}"))
    wp._resolved_text_cache = {-1: ("{serial()}", "999")}

    refresh_serials(doc)

    assert _resolved(wp) == ["1"]


def test_dispatch_never_raises(mocker):
    doc = Doc()
    _add_workpiece(doc, _sketch_with_text("{serial()}"))
    mocker.patch(
        "sketcher.core.serial_dispatch.advance",
        side_effect=OSError("disk full"),
    )

    on_job_dispatched(doc)


def test_refresh_keeps_user_scaled_size():
    doc = Doc()
    wp = _add_workpiece(doc, _sketch_with_text("{serial()}"))
    wp.regenerate_from_geometry_provider()
    natural = wp.size
    wp.set_size(natural[0] * 3, natural[1] * 2)
    resized = wp.size

    refresh_serials(doc)

    assert wp.size == pytest.approx(resized)


def test_refresh_current_doc_uses_registered_source():
    doc = Doc()
    wp = _add_workpiece(doc, _sketch_with_text("{serial()}"))
    wp._resolved_text_cache = {-1: ("{serial()}", "999")}
    set_doc_source(lambda: doc)
    try:
        refresh_current_doc()
    finally:
        set_doc_source(None)

    assert _resolved(wp) == ["1"]
