"""User-installed fonts for text boxes.

Font files live in the sketcher's addon data directory and are loaded
into raygeo's font database, which is what turns text into geometry.
raygeo cannot unload a face, so a removed font keeps working until
Rayforge restarts; it is only dropped from the list and from disk.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from raygeo.geo.shape.text import load_font_file

from rayforge.config import get_addon_data_dir

logger = logging.getLogger(__name__)

FONT_SUFFIXES = (".ttf", ".otf")

_families_by_file: dict[str, list[str]] = {}


def fonts_dir() -> Path:
    """The directory holding the installed font files."""
    path = get_addon_data_dir("sketcher") / "fonts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load(path: Path) -> list[str]:
    """Loads one font file once and remembers its family names."""
    key = str(path)
    if key not in _families_by_file:
        _families_by_file[key] = load_font_file(key)
    return _families_by_file[key]


def install_font(src: Path) -> list[str]:
    """
    Copies *src* into the fonts directory and loads it.

    Returns the family names it provides. Raises ValueError when the
    file is not a .ttf/.otf font or cannot be parsed; nothing is left
    behind in that case.
    """
    if src.suffix.lower() not in FONT_SUFFIXES:
        raise ValueError(f"Not a font file: {src.name}")
    dest = fonts_dir() / src.name
    shutil.copyfile(src, dest)
    try:
        return _load(dest)
    except (OSError, ValueError) as e:
        dest.unlink(missing_ok=True)
        raise ValueError(f"Cannot read font {src.name}: {e}") from e


def load_installed_fonts() -> None:
    """Loads every font in the fonts directory. Safe to call often:
    each file is loaded once per process, unreadable files are
    skipped."""
    for path in sorted(fonts_dir().iterdir()):
        if path.suffix.lower() not in FONT_SUFFIXES:
            continue
        try:
            _load(path)
        except (OSError, ValueError) as e:
            logger.warning(f"Skipping font {path.name}: {e}")


def list_custom_families() -> list[str]:
    """The family names provided by the installed fonts, sorted."""
    return sorted(
        {name for names in _families_by_file.values() for name in names}
    )


def is_custom_family(family: str) -> bool:
    return any(family in names for names in _families_by_file.values())


def remove_font(family: str) -> None:
    """Deletes every installed file providing *family*."""
    for key, names in list(_families_by_file.items()):
        if family in names:
            Path(key).unlink(missing_ok=True)
            del _families_by_file[key]
