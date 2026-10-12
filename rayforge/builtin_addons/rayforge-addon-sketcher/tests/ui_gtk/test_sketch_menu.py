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

from gi.repository import Gio
from sketcher.ui_gtk.menu import SketchMenu
from sketcher.ui_gtk.tools import ACTION_TOOL_MAP


def _actions(menu: Gio.MenuModel) -> set[str]:
    found = set()
    for index in range(menu.get_n_items()):
        action = menu.get_item_attribute_value(index, "action", None)
        if action is not None:
            found.add(action.get_string())
        for link in (Gio.MENU_LINK_SECTION, Gio.MENU_LINK_SUBMENU):
            child = menu.get_item_link(index, link)
            if child is not None:
                found |= _actions(child)
    return found


@pytest.mark.ui
def test_sketch_menu_offers_the_text_box_tool():
    assert "sketch.tool_text_box" in _actions(SketchMenu())
    assert "tool_text_box" in ACTION_TOOL_MAP
