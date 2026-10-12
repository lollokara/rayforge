from pathlib import Path

import pytest
from raygeo.geo.shape.text import FontConfig, text_to_geometry
from sketcher.core import fonts

FONT_FILE = Path(__file__).parents[1] / "assets" / "TestFont-Regular.ttf"


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    monkeypatch.setattr(fonts, "_families_by_file", {})
    return tmp_path


def test_fonts_dir_is_inside_addon_data(data_dir):
    assert fonts.fonts_dir() == data_dir / "sketcher" / "fonts"
    assert fonts.fonts_dir().is_dir()


def test_install_copies_and_lists_the_font():
    families = fonts.install_font(FONT_FILE)
    assert families
    assert (fonts.fonts_dir() / FONT_FILE.name).is_file()
    assert fonts.list_custom_families() == sorted(families)
    assert fonts.is_custom_family(families[0])


def test_installed_font_changes_layout():
    family = fonts.install_font(FONT_FILE)[0]
    custom = text_to_geometry("Hg", font_config=FontConfig(family=family))
    fallback = text_to_geometry("Hg", font_config=FontConfig())
    assert custom.rect() != fallback.rect()


def test_install_rejects_wrong_extension(tmp_path):
    bogus = tmp_path / "notes.txt"
    bogus.write_text("hello")
    with pytest.raises(ValueError):
        fonts.install_font(bogus)
    assert fonts.list_custom_families() == []


def test_install_rejects_unparsable_font_and_leaves_no_file(tmp_path):
    bogus = tmp_path / "broken.ttf"
    bogus.write_bytes(b"not a font")
    with pytest.raises(ValueError):
        fonts.install_font(bogus)
    assert not (fonts.fonts_dir() / "broken.ttf").exists()


def test_load_installed_fonts_picks_up_existing_files(monkeypatch):
    fonts.install_font(FONT_FILE)
    monkeypatch.setattr(fonts, "_families_by_file", {})
    assert fonts.list_custom_families() == []

    fonts.load_installed_fonts()

    assert fonts.list_custom_families()


def test_load_installed_fonts_skips_broken_files():
    (fonts.fonts_dir() / "broken.ttf").write_bytes(b"not a font")
    fonts.load_installed_fonts()
    assert fonts.list_custom_families() == []


def test_load_installed_fonts_survives_missing_dir(data_dir):
    fonts.load_installed_fonts()
    assert fonts.list_custom_families() == []


def test_remove_font_deletes_file_and_listing():
    family = fonts.install_font(FONT_FILE)[0]
    fonts.remove_font(family)
    assert not (fonts.fonts_dir() / FONT_FILE.name).exists()
    assert not fonts.is_custom_family(family)


def test_remove_unknown_font_is_a_noop():
    fonts.remove_font("No Such Family")


def test_is_known_family():
    system = ["DejaVu Sans", "Noto Serif"]
    assert fonts.is_known_family("dejavu sans", system)
    assert fonts.is_known_family("sans-serif", system)
    assert not fonts.is_known_family("Totally Missing", system)
    family = fonts.install_font(FONT_FILE)[0]
    assert fonts.is_known_family(family, system)
