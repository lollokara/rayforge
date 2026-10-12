import os
import sys

import pytest

if sys.platform.startswith("linux"):
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    if not os.environ.get("DISPLAY"):
        pytest.skip(
            "DISPLAY not set on Linux, skipping UI tests. Run with xvfb-run.",
            allow_module_level=True,
        )

from sketcher.core.serial import SerialCounter, load_counters, save_counters
from sketcher.ui_gtk.serial_settings import SerialSettingsPage


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    return tmp_path


@pytest.mark.ui
def test_page_has_title_and_icon():
    page = SerialSettingsPage()
    assert page.get_title()
    assert page.get_icon_name()


@pytest.mark.ui
def test_add_counter_persists():
    page = SerialSettingsPage()
    page.add_counter("batch")
    assert "batch" in load_counters()
    assert "batch" in page.counter_groups


@pytest.mark.ui
def test_add_blank_or_duplicate_counter_is_ignored():
    page = SerialSettingsPage()
    page.add_counter("  ")
    page.add_counter("batch")
    page.update_counter("batch", value=9)
    page.add_counter("batch")
    assert list(load_counters()) == ["batch"]
    assert load_counters()["batch"].value == 9


@pytest.mark.ui
def test_update_counter_persists():
    save_counters({"a": SerialCounter("a")})
    page = SerialSettingsPage()
    page.update_counter("a", step=5, padding=4, prefix="SN-")
    counter = load_counters()["a"]
    assert (counter.step, counter.padding, counter.prefix) == (5, 4, "SN-")


@pytest.mark.ui
def test_reset_counter_returns_to_start():
    save_counters({"a": SerialCounter("a", value=40, start=3)})
    page = SerialSettingsPage()
    page.reset_counter("a")
    assert load_counters()["a"].value == 3


@pytest.mark.ui
def test_delete_counter():
    save_counters({"a": SerialCounter("a"), "b": SerialCounter("b")})
    page = SerialSettingsPage()
    page.delete_counter("a")
    assert list(load_counters()) == ["b"]
    assert "a" not in page.counter_groups


@pytest.mark.ui
def test_page_survives_corrupt_file(data_dir):
    (data_dir / "sketcher").mkdir(parents=True, exist_ok=True)
    (data_dir / "sketcher" / "serials.json").write_text("{ nope")
    page = SerialSettingsPage()
    assert page.counter_groups == {}


@pytest.mark.ui
def test_corrupt_file_is_backed_up_before_edit(data_dir):
    folder = data_dir / "sketcher"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "serials.json").write_text("{ nope")
    page = SerialSettingsPage()

    page.add_counter("batch")

    assert (folder / "serials.json.bak").read_text() == "{ nope"
    assert "batch" in load_counters()


@pytest.mark.ui
def test_edits_refresh_the_open_document(mocker):
    refresh = mocker.patch(
        "sketcher.ui_gtk.serial_settings.refresh_current_doc"
    )
    save_counters({"a": SerialCounter("a", value=5)})
    page = SerialSettingsPage()

    page.update_counter("a", value=7)
    page.reset_counter("a")
    page.delete_counter("a")
    page.add_counter("b")

    assert refresh.call_count == 4
