"""Saved text presets: a name, a font and a text style.

Presets hold no text content and no path binding, so applying one to a
text box never changes what it says or what it follows.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from raygeo.geo.shape.text import FontConfig

from rayforge.config import get_addon_data_dir

from .entities.text_box import STYLE_DEFAULTS, TextBoxEntity
from .serial import backup_corrupt

logger = logging.getLogger(__name__)

PRESET_STYLE_KEYS = tuple(
    key
    for key in STYLE_DEFAULTS
    if key not in ("path_entity_id", "content_bottom")
)


@dataclass
class TextPreset:
    name: str
    font: dict[str, Any]
    style: dict[str, Any] = field(default_factory=dict)

    def font_config(self) -> FontConfig:
        return FontConfig.from_dict(self.font)


def presets_path() -> Path:
    return get_addon_data_dir("sketcher") / "text_presets.json"


def preset_from_entity(name: str, entity: TextBoxEntity) -> TextPreset:
    """Captures the font and style of *entity* under *name*."""
    style = entity.get_style()
    return TextPreset(
        name,
        entity.font_config.to_dict(),
        {key: style[key] for key in PRESET_STYLE_KEYS},
    )


def _parse(item: Any) -> TextPreset | None:
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    font = item.get("font")
    style = item.get("style", {})
    if not isinstance(name, str) or not name:
        return None
    if not isinstance(font, dict) or not isinstance(style, dict):
        return None
    return TextPreset(
        name,
        font,
        {key: style[key] for key in PRESET_STYLE_KEYS if key in style},
    )


def load_presets(backup_unreadable: bool = False) -> list[TextPreset]:
    """All saved presets, sorted by name. A missing or unreadable file
    yields an empty list; with *backup_unreadable* the unreadable file
    is first moved aside so the caller can overwrite it safely."""
    try:
        data = json.loads(presets_path().read_text(encoding="utf-8"))
        items = data["presets"]
    except FileNotFoundError:
        return []
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"Cannot read text presets: {e}")
        if backup_unreadable and presets_path().exists():
            backup_corrupt(presets_path())
        return []
    if not isinstance(items, list):
        if backup_unreadable:
            backup_corrupt(presets_path())
        return []
    presets = [p for p in map(_parse, items) if p is not None]
    return sorted(presets, key=lambda preset: preset.name.lower())


def _write(presets: list[TextPreset]) -> None:
    path = presets_path()
    tmp = path.with_suffix(".json.tmp")
    payload = {
        "presets": [
            {"name": p.name, "font": p.font, "style": p.style} for p in presets
        ]
    }
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def save_preset(preset: TextPreset) -> None:
    """Saves *preset*, replacing any preset of the same name."""
    others = [p for p in load_presets(True) if p.name != preset.name]
    _write(others + [preset])


def delete_preset(name: str) -> None:
    """Deletes the preset called *name*, if there is one."""
    presets = load_presets(True)
    remaining = [p for p in presets if p.name != name]
    if len(remaining) != len(presets):
        _write(remaining)
