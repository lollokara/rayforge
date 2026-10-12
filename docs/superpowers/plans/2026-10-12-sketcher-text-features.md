# Sketcher Text Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Sketcher Text Box tool (`G+T`) with text transforms, knock-out, round text, custom fonts, saved presets and persistent serial numbers, so laser-ready text can be produced from the builtin sketcher addon.

**Architecture:** All style lives as plain attributes on `TextBoxEntity`, and every consumer (canvas, stroke output, fill output) goes through `TextBoxEntity.to_geometry` / `to_fill_geometry`, so canvas and laser output cannot diverge. Persistent data (fonts, presets, serial counters) lives under `get_addon_data_dir("sketcher")`. Core gains one public hook, `job_dispatched(doc, kind)`, which the sketcher uses to advance serial counters; custom fonts need one new raygeo function, `load_font_file`, delivered by a separate raygeo PR.

**Tech Stack:** Python 3, GTK4 / libadwaita (PyGObject), raygeo (Rust/PyO3: `Geometry`, `Matrix`, `FontConfig`, `text_to_geometry`), pluggy hooks, blinker signals, pytest (+ pytest-mock, pytest-asyncio), pixi.

**Spec:** `docs/superpowers/specs/2026-10-12-sketcher-text-features-design.md`
(read-only analysis the spec is based on:
`/private/tmp/claude-501/-Users-lorenzo-orca-workspaces-rayforge-SVG-Text-plugin/588f8f9c-64a8-422f-bec4-02a82a8b40ba/scratchpad/sketcher-text-box-plan.md`)

## Global Constraints

- Extend the builtin sketcher addon; do not create a separate addon.
- Python: PEP8, maximum line length 79 characters. Keep functions small.
- Wrap every user-visible string with gettext `_()`
(`from gettext import gettext as _` at the top of the file).
- Imports go at the top of the file, never inside functions. (The existing
lazy imports inside the hook functions of `sketcher/frontend.py` and
`sketcher/worker.py` stay as they are; new imports go at the top.)
- Never mark changes with inline comments. Retain existing formatting,
docstrings, comments and logging.
- Run `pixi run lint` and fix every error before running tests. Run targeted
tests only (`pixi run test <path>`), never the full suite prematurely.
- Never pipe CLI output through `head`.
- Do not make changes unrelated to the task.
- New style attributes serialize only when non-default and load with
`data.get`; `FORMAT_VERSION` stays `1`.
- Style is not stored in `FontConfig.extra` (its `copy()` drops non-string
values).
- `PLUGIN_API_VERSION` goes 21 to 22; sketcher manifest `api_version` goes 19
to 22.
- Serial advance: after a send is handed to the machine successfully; G-code
export counts; framing, `pointer_dry_run`, cancelled and failed jobs,
sanity checks and previews do not.
- Counters are global and shared; the file is re-read on every advance.
- Fonts are not embedded in projects; a missing font shows a warning.
- Out of scope: batch or array serial mode, chained multi-segment paths,
embedding fonts, single-line (Hershey) fonts.
- Commit steps are plan steps: an executor commits only when its coordinator  
says so. Commit messages end with NO `Co-Authored-By:`

### Conventions used below

- `SK` = `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher`
- `SKT` = `rayforge/builtin_addons/rayforge-addon-sketcher/tests`
- Backend test: `pixi run test <path>::<test>`. UI test (marked
`@pytest.mark.ui`, needs Linux + xvfb): `pixi run uitest <path>`. The
default pytest options exclude `ui` tests, so a UI test run through
`pixi run test` reports "deselected", not "passed".
- Executor tiers: **ANTIGRAVITY-LOW** (docs, catalogs, mechanical edits,
simple UI rows) and **SONNET** (geometry, commands, hook, serial logic,
anything needing judgement).

### Wave map (for the coordinator)

`SK/ui_gtk/font_properties.py` is edited by Tasks 5, 7, 11, 15, 17 and 22;
those six run strictly in that order. `SK/core/entities/text_box.py` is
edited by Tasks 2, 4, 6 and 10, in that order.


| Wave                     | Tasks                               |
| ------------------------ | ----------------------------------- |
| A                        | 1, 2, 8, 12 (external repo), 18, 19 |
| B                        | 3, 4, 9, 16, 20                     |
| C                        | 5, 6, 21                            |
| D                        | 7, 10                               |
| E                        | 11                                  |
| F (after raygeo release) | 13, then 14, then 15                |
| G                        | 17, then 22                         |
| H                        | 23, then 24; 25; 26                 |


## Review Focus

1. **Text longer than its path.** A user binds a long string to a short line
 or arc. Expected: glyphs continue along the end tangent (open path) or
 wrap around (circle) instead of piling up on the end point. Pinned by
 `test_text_longer_than_open_path_extends_along_tangent` (Task 9).
2. **Bound path entity deleted.** The user deletes the line or circle a text
 box follows. Expected: the text falls back to its frame layout, no crash,
 and undoing the delete restores the binding. Pinned by
 `test_missing_path_entity_falls_back_to_frame` (Task 10).
3. **Hand-edited or corrupt persisted data.** A project file with
 `"rotation": "abc"`, or a truncated `serials.json` / `text_presets.json`.
 Expected: bad style values load as defaults; a corrupt serial file is kept
 as `serials.json.bak` and counting restarts instead of crashing a job.
 Pinned by `test_from_dict_ignores_invalid_style_values` (Task 2),
 `test_advance_backs_up_corrupt_file` (Task 19) and
 `test_corrupt_file_returns_empty_list` (Task 16).
4. **Empty or whitespace-only content with style flags on.** `" "` with
 mirror, vertical, rotation, knock-out or a path. Expected: empty or
 plate-only geometry, no exception. Pinned by
 `test_blank_content_with_all_flags_does_not_raise` (Task 4) and
 `test_blank_text_on_path_is_empty` (Task 9).
5. **A job that does nothing.** Sending a document with no operations, or a
 dry run on a machine without pointer offset (which burns like a regular
 send). Expected: the empty job does not advance serials; the offset-less
 "dry run" does. Pinned by `test_empty_job_does_not_dispatch` and
 `test_dry_run_without_pointer_offset_dispatches` (Task 18).

Known accepted limits (from the spec's Risks, no test): the in-place edit
overlay in `TextBoxTool.draw_overlay` still draws plain left-to-right text
while a transformed box is being edited; knock-out drops the counters of O,
A, B; two Rayforge windows advancing at the same instant can race (no file
lock).

---

### Task 1: Canvas glyphs come from `TextBoxEntity.to_geometry` (Phase 0)

Executor tier: ANTIGRAVITY-LOW
Depends on: none
Parallel-safe with: Task 2, 3, 8, 9, 12, 16, 18, 19, 20

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/renderer.py:10` (drop import) and `:582-613` (`_define_text_box_path`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_text_box.py`

**Interfaces:**

- Consumes: `TextBoxEntity.to_geometry(registry, resolved_content=None) -> Geometry` (exists, `SK/core/entities/text_box.py:338`); `geometry_to_cairo(geo, ctx)` (already imported at `renderer.py:13`).
- Produces: `SketchRenderer._define_text_box_path` draws exactly what `entity.to_geometry` returns. Every later geometry task relies on this.

- [ ] **Step 1: Write the failing test**

Append to `SKT/ui_gtk/test_text_box.py` (it already imports `Mock`,
`pytest`, `TextBoxEntity`, `SketchRenderer` and defines the
`sketch_with_text_box` fixture returning `(sketch, tb_id)`):

```python
@pytest.mark.ui
def test_define_text_box_path_uses_entity_geometry(
    sketch_with_text_box, mocker
):
    """The canvas must draw what TextBoxEntity.to_geometry returns."""
    sketch, tb_id = sketch_with_text_box
    entity = sketch.registry.get_entity(tb_id)
    renderer = Mock()
    renderer.element.sketch = sketch
    renderer._safe_get_point = sketch.registry.get_point
    sentinel = object()
    mocker.patch.object(TextBoxEntity, "to_geometry", return_value=sentinel)
    to_cairo = mocker.patch("sketcher.ui_gtk.renderer.geometry_to_cairo")
    ctx = Mock()

    assert SketchRenderer._define_text_box_path(renderer, ctx, entity)

    to_cairo.assert_called_once_with(sentinel, ctx)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_text_box.py::test_define_text_box_path_uses_entity_geometry`
Expected: FAIL, `geometry_to_cairo` was called with a `Geometry`, not the sentinel.

- [ ] **Step 3: Replace the duplicated layout**

In `SK/ui_gtk/renderer.py` replace the whole `_define_text_box_path` method
with:

```python
    def _define_text_box_path(
        self, ctx: cairo.Context, entity: TextBoxEntity
    ) -> bool:
        if not entity.content:
            return False

        p_origin = self._safe_get_point(entity.origin_id)
        p_width = self._safe_get_point(entity.width_id)
        p_height = self._safe_get_point(entity.height_id)

        if not (p_origin and p_width and p_height):
            return False

        geometry_to_cairo(
            entity.to_geometry(self.element.sketch.registry), ctx
        )
        return True
```

Then delete line 10, `from raygeo.geo.shape.text import text_to_geometry`
(it has no other user in this file; pyflakes fails otherwise).

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_text_box.py`
Expected: PASS (all tests in the file).
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/constraints/test_text_rendering.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/renderer.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_text_box.py
git commit -m "refactor(sketcher): draw text boxes from entity geometry"
```

---

### Task 2: Style data model on `TextBoxEntity` (Phase 1)

Executor tier: SONNET
Depends on: none
Parallel-safe with: Task 1, 8, 12, 18, 19, 20

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py` (module top, `__init__` `:28-49`, `geometry_signature` `:199-209`, `rewrite_offsets_from` `:211-220`, `to_dict` `:361-375`, `from_dict` `:377-394`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`

**Interfaces:**

- Consumes: nothing new.
- Produces (in `sketcher.core.entities.text_box`):
  - `STYLE_DEFAULTS: dict[str, Any]` with keys `mirrored` (bool, False),
  `reverse` (bool, False), `vertical` (bool, False), `rotation` (float
  degrees, 0.0), `knockout` (bool, False), `knockout_margin` (float mm,
  2.0), `path_entity_id` (`int | None`, None), `path_side` (`"outside"` |
  `"inside"`), `path_align` (`"start"` | `"center"` | `"end"`, default
  `"center"`), `path_offset` (float mm, 0.0), `content_bottom` (str, "").
  - Attributes of those names on every `TextBoxEntity`.
  - `TextBoxEntity.get_style() -> dict[str, Any]` (all keys).
  - `TextBoxEntity.set_style(style: dict[str, Any]) -> None` (partial dicts
  allowed; unknown keys and invalid values are ignored).

- [ ] **Step 1: Write the failing tests**

Append to `SKT/core/entities/test_text_box_entity.py`, and add
`from unittest.mock import Mock` and
`from sketcher.core.entities.text_box import STYLE_DEFAULTS` to its imports:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`
Expected: collection error, `cannot import name 'STYLE_DEFAULTS'`.

- [ ] **Step 3: Implement the style model**

In `SK/core/entities/text_box.py`, after `logger = logging.getLogger(__name__)`
add:

```python
STYLE_DEFAULTS: dict[str, Any] = {
    "mirrored": False,
    "reverse": False,
    "vertical": False,
    "rotation": 0.0,
    "knockout": False,
    "knockout_margin": 2.0,
    "path_entity_id": None,
    "path_side": "outside",
    "path_align": "center",
    "path_offset": 0.0,
    "content_bottom": "",
}

_STYLE_CHOICES = {
    "path_side": ("outside", "inside"),
    "path_align": ("start", "center", "end"),
}


def _is_valid_style_value(key: str, value: Any) -> bool:
    if key == "path_entity_id":
        return value is None or (
            isinstance(value, int) and not isinstance(value, bool)
        )
    if key in _STYLE_CHOICES:
        return value in _STYLE_CHOICES[key]
    default = STYLE_DEFAULTS[key]
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, float):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    return isinstance(value, str)
```

In `__init__`, after `self.fill_color: ColorRGBA | None = None` add:

```python
        self.mirrored: bool = False
        self.reverse: bool = False
        self.vertical: bool = False
        self.rotation: float = 0.0
        self.knockout: bool = False
        self.knockout_margin: float = 2.0
        self.path_entity_id: EntityID | None = None
        self.path_side: str = "outside"
        self.path_align: str = "center"
        self.path_offset: float = 0.0
        self.content_bottom: str = ""
```

After `set_fill_color` add:

```python
    def get_style(self) -> dict[str, Any]:
        """Returns every style attribute, keyed like STYLE_DEFAULTS."""
        return {key: getattr(self, key) for key in STYLE_DEFAULTS}

    def set_style(self, style: dict[str, Any]) -> None:
        """Applies the known, valid entries of *style*; anything else
        is ignored so stale or hand-edited data cannot break layout."""
        for key, value in style.items():
            if key not in STYLE_DEFAULTS:
                continue
            if not _is_valid_style_value(key, value):
                continue
            if isinstance(STYLE_DEFAULTS[key], float):
                value = float(value)
            setattr(self, key, value)
```

Replace the body of `geometry_signature` (keep its docstring):

```python
        font = self.font_config
        return (
            super().geometry_signature(registry)
            + (
                self.content,
                font.family,
                font.size,
                font.bold,
                font.italic,
            )
            + tuple(self.get_style().values())
        )
```

In `rewrite_offsets_from`, after `self.fill_color = template.fill_color` add:

```python
        self.set_style(template.get_style())
```

In `to_dict`, before `return data` add:

```python
        for key, default in STYLE_DEFAULTS.items():
            value = getattr(self, key)
            if value != default:
                data[key] = value
```

In `from_dict`, after `entity.fill_color = fill_color` add:

```python
        entity.set_style(data)
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`
Expected: PASS.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_array_text_template.py`
Expected: PASS (array sync uses `geometry_signature`).

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py
git commit -m "feat(sketcher): add style attributes to text boxes"
```

---

### Task 3: Undoable style changes in `ModifyTextPropertyCommand` (Phase 1)

Executor tier: SONNET
Depends on: Task 2
Parallel-safe with: Task 1, 4, 8, 9, 12, 16, 18, 19, 20

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/commands/text_property.py` (`__init__` `:26-51`, `capture_pre_edit_state` `:96-127`, `_do_execute` `:129-189`, `_do_undo` `:258-307`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/commands/test_text_property_cmd.py`

**Interfaces:**

- Consumes: `TextBoxEntity.get_style()`, `TextBoxEntity.set_style(style)` (Task 2).
- Produces: `ModifyTextPropertyCommand(sketch, text_entity_id, new_content, new_font_config, new_style: dict[str, Any] | None = None)`; public attributes `new_style` and `old_style: dict[str, Any]`. `new_style=None` leaves the style untouched.

- [ ] **Step 1: Write the failing tests**

Append to `SKT/core/commands/test_text_property_cmd.py` (the
`sketch_with_text_box` fixture returns `(sketch, tb_id)`; `HistoryManager`
is already imported):

```python
def test_style_change_execute_and_undo(sketch_with_text_box):
    sketch, tb_id = sketch_with_text_box
    tb = sketch.registry.get_entity(tb_id)
    cmd = ModifyTextPropertyCommand(
        sketch,
        tb_id,
        tb.content,
        tb.font_config,
        new_style={"mirrored": True, "rotation": 90.0},
    )

    cmd.execute()
    assert tb.mirrored is True
    assert tb.rotation == 90.0

    cmd.undo()
    assert tb.mirrored is False
    assert tb.rotation == 0.0


def test_command_without_style_leaves_style_untouched(
    sketch_with_text_box,
):
    sketch, tb_id = sketch_with_text_box
    tb = sketch.registry.get_entity(tb_id)
    tb.mirrored = True
    cmd = ModifyTextPropertyCommand(
        sketch, tb_id, "Changed", tb.font_config
    )

    cmd.execute()
    assert tb.mirrored is True
    cmd.undo()
    assert tb.mirrored is True


def test_style_change_redo_with_history_manager(sketch_with_text_box):
    sketch, tb_id = sketch_with_text_box
    tb = sketch.registry.get_entity(tb_id)
    history = HistoryManager()
    history.execute(
        ModifyTextPropertyCommand(
            sketch,
            tb_id,
            tb.content,
            tb.font_config,
            new_style={"vertical": True},
        )
    )
    history.undo()
    assert tb.vertical is False
    history.redo()
    assert tb.vertical is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/commands/test_text_property_cmd.py::test_style_change_execute_and_undo`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'new_style'`.

- [ ] **Step 3: Implement the style snapshot**

In `SK/core/commands/text_property.py` change the constructor signature and
add two attributes:

```python
    def __init__(
        self,
        sketch: Sketch,
        text_entity_id: EntityID,
        new_content: str,
        new_font_config: FontConfig,
        new_style: dict[str, Any] | None = None,
    ):
        super().__init__(sketch, _("Modify Text Property"))
        self.text_entity_id = text_entity_id
        self.new_content = new_content
        self.new_font_config = new_font_config
        self.new_style = new_style
        self.old_style: dict[str, Any] = {}
```

(the remaining attribute assignments of `__init__` stay as they are).

In `capture_pre_edit_state`, after
`self.old_font_config = text_entity.font_config.copy()` add:

```python
        self.old_style = text_entity.get_style()
```

In `_do_execute`, after
`text_entity.font_config = self.new_font_config.copy()` add:

```python
        if self.new_style is not None:
            text_entity.set_style(self.new_style)
```

In `_do_undo`, after the block

```python
        if self.old_font_config is not None:
            text_entity.font_config = self.old_font_config.copy()
```

add:

```python
        if self.new_style is not None:
            text_entity.set_style(self.old_style)
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/commands/test_text_property_cmd.py`
Expected: PASS (new and existing tests).

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/commands/text_property.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/commands/test_text_property_cmd.py
git commit -m "feat(sketcher): make text style changes undoable"
```

---

### Task 4: Transform geometry: reverse, vertical, mirror, rotation (Phase 2)

Executor tier: SONNET
Depends on: Task 1, Task 2
Parallel-safe with: Task 3, 8, 9, 12, 16, 18, 19, 20

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py` (import `:7`, `get_natural_size` `:128-153`, `to_geometry` `:338-359`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`

**Interfaces:**

- Consumes: style attributes and `set_style` (Task 2). raygeo:
`Matrix.scale(sx, sy, center=None)`, `Matrix.rotation(angle_deg, center=None)`,
`Matrix.translation(tx, ty)`, `Geometry.transform(matrix) -> Geometry`
(in place, returns the geometry), `Geometry.extend(other)`,
`Geometry.rect() -> (min_x, min_y, max_x, max_y)`,
`FontConfig.get_font_metrics() -> (ascent, descent, height)`.
- Produces:
  - `TextBoxEntity._natural_layout(text: str) -> tuple[Geometry, float, float, float]`
  returning `(geometry, width, min_y, height)` in natural space (mm, Y up,
  baseline origin) with reverse, vertical and mirror applied.
  - `TextBoxEntity._frame_glyphs(registry, text: str) -> Geometry`: glyphs
  mapped into the frame and rotated. Tasks 6 and 10 extend it.
  - `TextBoxEntity.get_natural_size()` honours `vertical`.
  - Fixed order: reverse, lay out, mirror, `map_to_frame`, rotate about the
  frame centre.

- [ ] **Step 1: Write the failing tests**

Append to `SKT/core/entities/test_text_box_entity.py`, and add
`from raygeo.geo.shape.text import text_to_geometry` to the existing
`raygeo.geo.shape.text` import:

```python
def _natural_box(registry, content="FL", **style):
    """A text box whose frame equals the natural size of its content,
    so map_to_frame is an identity scale."""
    probe = TextBoxEntity(0, 0, 0, 0, content, FontConfig())
    probe.set_style(style)
    width, height = probe.get_natural_size()
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(width, 0)
    p3 = registry.add_point(0, height)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, content, FontConfig())
    )
    box.set_style(style)
    return box, width, height


def _mean_x(geo):
    xs = [x for ring in geo.to_polygons(0.01) for x, _ in ring]
    return sum(xs) / len(xs)


def test_default_style_matches_plain_layout(registry):
    box, width, _ = _natural_box(registry)
    plain = text_to_geometry("FL", font_config=FontConfig())
    _, min_y, _, max_y = plain.rect()
    expected = plain.map_to_frame(
        (0.0, 0.0),
        (width, 0.0),
        (0.0, max_y - min_y),
        anchor_x=0.0,
        stable_src_width=FontConfig().get_text_width("FL"),
        anchor_y=min_y,
        stable_src_height=max_y - min_y,
    )
    assert box.to_geometry(registry).rect() == pytest.approx(
        expected.rect()
    )


def test_mirror_reflects_about_frame_centre(registry):
    plain, width, _ = _natural_box(registry, "L")
    mirrored, _, _ = _natural_box(registry, "L", mirrored=True)
    r0 = plain.to_geometry(registry).rect()
    r1 = mirrored.to_geometry(registry).rect()
    assert r1[0] == pytest.approx(width - r0[2], abs=1e-6)
    assert r1[2] == pytest.approx(width - r0[0], abs=1e-6)
    assert (r1[1], r1[3]) == pytest.approx((r0[1], r0[3]))
    plain_side = _mean_x(plain.to_geometry(registry)) - (r0[0] + r0[2]) / 2
    mirror_side = (
        _mean_x(mirrored.to_geometry(registry)) - (r1[0] + r1[2]) / 2
    )
    assert plain_side * mirror_side < 0


def test_reverse_lays_out_characters_backwards(registry):
    reversed_box, _, _ = _natural_box(registry, "AB", reverse=True)
    plain_box, _, _ = _natural_box(registry, "BA")
    assert reversed_box.to_geometry(registry).rect() == pytest.approx(
        plain_box.to_geometry(registry).rect()
    )


def test_vertical_is_taller_than_wide(registry):
    box, width, height = _natural_box(registry, "ABC", vertical=True)
    assert height > width
    min_x, min_y, max_x, max_y = box.to_geometry(registry).rect()
    assert max_y - min_y > max_x - min_x


def test_rotation_360_is_identity(registry):
    plain, _, _ = _natural_box(registry)
    turned, _, _ = _natural_box(registry, rotation=360.0)
    assert turned.to_geometry(registry).rect() == pytest.approx(
        plain.to_geometry(registry).rect(), abs=1e-6
    )


def test_rotation_180_is_point_reflection(registry):
    plain, width, height = _natural_box(registry)
    turned, _, _ = _natural_box(registry, rotation=180.0)
    r0 = plain.to_geometry(registry).rect()
    r1 = turned.to_geometry(registry).rect()
    assert r1 == pytest.approx(
        (width - r0[2], height - r0[3], width - r0[0], height - r0[1]),
        abs=1e-6,
    )


def test_rotation_90_swaps_extents(registry):
    plain, _, _ = _natural_box(registry)
    turned, _, _ = _natural_box(registry, rotation=90.0)
    r0 = plain.to_geometry(registry).rect()
    r1 = turned.to_geometry(registry).rect()
    assert r1[2] - r1[0] == pytest.approx(r0[3] - r0[1], abs=1e-6)
    assert r1[3] - r1[1] == pytest.approx(r0[2] - r0[0], abs=1e-6)


def test_blank_content_with_all_flags_does_not_raise(registry):
    p1 = registry.add_point(0, 0)
    p2 = registry.add_point(10, 0)
    p3 = registry.add_point(0, 10)
    box = registry.get_entity(
        registry.add_text_box(p1, p2, p3, " ", FontConfig())
    )
    box.set_style(
        {"mirrored": True, "reverse": True, "vertical": True, "rotation": 30.0}
    )
    assert isinstance(box.to_geometry(registry), Geometry)
    assert box.get_natural_size()[0] >= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py -k "mirror or reverse or vertical or rotation"`
Expected: FAIL (mirror, reverse, vertical and rotation have no effect yet).

- [ ] **Step 3: Implement the layout pipeline**

In `SK/core/entities/text_box.py` change line 7 to:

```python
from raygeo.geo import Geometry, Matrix
```

Replace the body of `get_natural_size` after its docstring with:

```python
        text = content if content is not None else self.content

        if not text:
            return 10.0, self.font_config.size

        _, width, _, height = self._natural_layout(text)
        return max(width, 1.0), max(height, 1.0)
```

Add these methods directly after `get_natural_size`:

```python
    def _vertical_layout(
        self, text: str
    ) -> tuple[Geometry, float, float, float]:
        """Stacks upright characters top to bottom, each centred on
        the column."""
        font = self.font_config
        line_height = font.get_font_metrics()[2] or font.size
        column = (
            max((font.get_text_width(ch) for ch in text), default=0.0) or 1.0
        )
        geo = Geometry()
        for i, ch in enumerate(text):
            glyph = text_to_geometry(ch, font_config=font)
            dx = (column - font.get_text_width(ch)) / 2.0
            glyph.transform(Matrix.translation(dx, -i * line_height))
            geo.extend(glyph)
        _, min_y, _, max_y = geo.rect()
        return geo, column, min_y, max_y - min_y

    def _natural_layout(
        self, text: str
    ) -> tuple[Geometry, float, float, float]:
        """
        Lays *text* out in natural space (mm, Y up, baseline origin)
        with reverse, vertical and mirror applied, in that order.

        Returns (geometry, width, min_y, height); width is the advance
        width (or the column width for vertical text).
        """
        if self.reverse:
            text = text[::-1]
        if self.vertical:
            geo, width, min_y, height = self._vertical_layout(text)
        else:
            geo = text_to_geometry(text, font_config=self.font_config)
            _, min_y, _, max_y = geo.rect()
            width = self.font_config.get_text_width(text) or 1.0
            height = max_y - min_y
        if self.mirrored:
            geo.transform(
                Matrix.scale(-1.0, 1.0, center=(width / 2.0, 0.0))
            )
        return geo, width, min_y, height

    def _frame_glyphs(
        self, registry: "EntityRegistry", text: str
    ) -> Geometry:
        """Maps the natural layout into the frame, then rotates it
        about the frame centre."""
        origin, pw, ph = self._build_frame_for_content(registry, text)
        geo, width, min_y, height = self._natural_layout(text)
        geo = geo.map_to_frame(
            origin,
            pw,
            ph,
            anchor_x=0.0,
            stable_src_width=width,
            anchor_y=min_y,
            stable_src_height=height,
        )
        if self.rotation:
            centre = ((pw[0] + ph[0]) / 2.0, (pw[1] + ph[1]) / 2.0)
            geo.transform(Matrix.rotation(self.rotation, center=centre))
        return geo
```

Replace the body of `to_geometry` after its docstring with:

```python
        text = (
            resolved_content if resolved_content is not None else self.content
        )
        return self._frame_glyphs(registry, text)
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`
Expected: PASS.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/commands/test_text_property_cmd.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_text_templates.py`
Expected: PASS (natural size and resolved content still behave).

If `test_rotation_90_swaps_extents` passes but a later visual check shows
text turning clockwise for a positive angle, that is raygeo's convention;
do not negate the angle.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py
git commit -m "feat(sketcher): mirror, reverse, vertical and rotated text"
```

---

### Task 5: Transform rows in Font Properties and caret guard (Phase 2)

Executor tier: SONNET
Depends on: Task 3, Task 4
Parallel-safe with: Task 6, 8, 9, 12, 16, 18, 19, 20, 21

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/tools/text_box_tool.py` (`_update_cursor_from_click` `:748`, `apply_font_change` `:834`)
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/tools/test_text_box_tool.py`

**Interfaces:**

- Consumes: `ModifyTextPropertyCommand(..., new_style=...)` (Task 3);
`TextBoxEntity.get_style()/set_style()` (Task 2);
`AngleSpinRow(title, subtitle=None, *, lower=-360.0, upper=360.0, digits=1, **kwargs)`
from `rayforge.ui_gtk.shared.pref_rows` with `get_value()`, `set_value()`
and a `value_changed` signal (`.connect(handler)`, handler receives the row).
- Produces:
  - `FontPropertiesWidget._add_switch_row(title: str, handler) -> Gtk.Switch`
  - `FontPropertiesWidget._get_style_from_ui() -> dict[str, Any]`
  - `FontPropertiesWidget._update_style_ui(entity: TextBoxEntity) -> None`
  - `FontPropertiesWidget._on_style_changed(*args) -> None`
  - widget attributes `mirror_switch`, `reverse_switch`, `vertical_switch`,
  `upside_down_switch`, `rotation_row`
  - `TextBoxTool.apply_font_change(new_font_config, new_style: dict | None = None) -> bool`
  - test fixture `widget_with_box` in `SKT/ui_gtk/test_font_properties.py`
  returning `(widget, sketch, tb_id)`; Tasks 7, 11, 15, 17 and 22 reuse it.

- [ ] **Step 1: Write the failing widget tests**

Create `SKT/ui_gtk/test_font_properties.py`:

```python
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
    widget._on_style_changed()

    assert entity.mirrored is True
    assert entity.rotation == 90.0

    widget.editor.history_manager.undo()
    assert entity.mirrored is False
    assert entity.rotation == 0.0


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
```

Append to `SKT/ui_gtk/tools/test_text_box_tool.py` (it defines the
`text_box_tool` and `mock_element` fixtures; add
`from raygeo.geo.shape.text import FontConfig` and
`from sketcher.core.entities import TextBoxEntity` to the imports if they
are not there yet):

```python
@pytest.mark.ui
@pytest.mark.parametrize(
    "style",
    [
        {"mirrored": True},
        {"vertical": True},
        {"rotation": 90.0},
        {"reverse": True},
        {"path_entity_id": 3},
    ],
)
def test_click_keeps_caret_on_transformed_text(
    text_box_tool, mock_element, style
):
    entity = TextBoxEntity(5, 1, 2, 3, "Hello", FontConfig())
    entity.set_style(style)
    mock_element.sketch.registry.get_entity = Mock(return_value=entity)
    text_box_tool.editing_entity_id = 5
    text_box_tool.text_buffer = "Hello"
    text_box_tool.cursor_pos = 5

    text_box_tool._update_cursor_from_click(0.0, 0.0)

    assert text_box_tool.cursor_pos == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/tools/test_text_box_tool.py`
Expected: FAIL, `FontPropertiesWidget` has no attribute `mirror_switch`;
the caret test moves the cursor to 0.

- [ ] **Step 3: Add the rows to the widget**

In `SK/ui_gtk/font_properties.py`:

Change the typing and pref-row imports to:

```python
from typing import TYPE_CHECKING, Any
```

```python
from rayforge.ui_gtk.shared.pref_rows import AngleSpinRow, SpinRow
```

At the end of `_build_ui` add:

```python
        self.mirror_switch = self._add_switch_row(
            _("Mirror"), self._on_style_changed
        )
        self.reverse_switch = self._add_switch_row(
            _("Reverse Characters"), self._on_style_changed
        )
        self.vertical_switch = self._add_switch_row(
            _("Vertical"), self._on_style_changed
        )
        self.upside_down_switch = self._add_switch_row(
            _("Upside Down"), self._on_upside_down_changed
        )

        self.rotation_row = AngleSpinRow(_("Rotation"))
        self.rotation_row.value_changed.connect(self._on_style_changed)
        self.add(self.rotation_row)

    def _add_switch_row(self, title: str, handler) -> Gtk.Switch:
        """Adds an action row with a switch and returns the switch."""
        row = Adw.ActionRow()
        row.set_title(title)
        switch = Gtk.Switch()
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect("state-set", handler)
        row.add_suffix(switch)
        row.set_activatable_widget(switch)
        self.add(row)
        return switch
```

In `set_text_entity`, replace the last two lines

```python
        self.set_visible(True)
        self._update_ui_from_model(entity.font_config)
```

with:

```python
        self.set_visible(True)
        self._update_ui_from_model(entity.font_config)
        self._update_style_ui(entity)
```

After `_get_font_config_from_ui` add:

```python
    def _update_style_ui(self, entity: TextBoxEntity):
        """Updates the style widgets from the text entity."""
        self._in_update = True
        try:
            self.mirror_switch.set_active(entity.mirrored)
            self.reverse_switch.set_active(entity.reverse)
            self.vertical_switch.set_active(entity.vertical)
            self.rotation_row.set_value(entity.rotation)
            self.upside_down_switch.set_active(entity.rotation == 180.0)
        finally:
            self._in_update = False

    def _get_style_from_ui(self) -> dict[str, Any]:
        """Collects the style values shown by the widget."""
        return {
            "mirrored": self.mirror_switch.get_active(),
            "reverse": self.reverse_switch.get_active(),
            "vertical": self.vertical_switch.get_active(),
            "rotation": self.rotation_row.get_value(),
        }

    def _on_style_changed(self, *args):
        """Handles a change of any style row."""
        if self._in_update or self._text_entity_id is None:
            return
        self._apply_font_config()

    def _on_upside_down_changed(self, switch, state):
        """Maps the upside-down switch onto a 180 degree rotation."""
        if self._in_update or self._text_entity_id is None:
            return
        self._in_update = True
        try:
            self.rotation_row.set_value(180.0 if state else 0.0)
        finally:
            self._in_update = False
        self._apply_font_config()
```

In `_apply_font_config`, replace everything from
`new_font_config = self._get_font_config_from_ui()` to the end of the
method with (the long explanatory comment stays where it is, above
`text_tool = ...`):

```python
        new_font_config = self._get_font_config_from_ui()
        new_style = self._get_style_from_ui()

        # When the text box is being edited, fold the font change into the
        # active edit session instead of pushing a separate command: the
        # live resize performed while typing mutates geometry outside the
        # command system, so a standalone command would snapshot that
        # mutated state as its pre-state and restore it on undo.
        text_tool = sketch_element.tools.get("text_box")
        if (
            text_tool
            and text_tool.editing_entity_id == self._text_entity_id
            and text_tool.apply_font_change(new_font_config, new_style)
        ):
            return

        cmd = ModifyTextPropertyCommand(
            sketch=sketch_element.sketch,
            text_entity_id=self._text_entity_id,
            new_content=entity.content,
            new_font_config=new_font_config,
            new_style=new_style,
        )
        self.editor.history_manager.execute(cmd)
```

- [ ] **Step 4: Update the text tool**

In `SK/ui_gtk/tools/text_box_tool.py`, in `_update_cursor_from_click`,
directly after

```python
        if not isinstance(entity, TextBoxEntity):
            return
```

add:

```python
        # shortcut: caret placement assumes plain left-to-right text
        # along the width edge, upgrade when transformed text needs
        # in-place caret positioning
        if (
            entity.mirrored
            or entity.reverse
            or entity.vertical
            or entity.rotation
            or entity.path_entity_id is not None
        ):
            return
```

Change `apply_font_change` to accept and apply the style. Its signature
becomes:

```python
    def apply_font_change(
        self,
        new_font_config: FontConfig,
        new_style: dict[str, Any] | None = None,
    ) -> bool:
```

and the block

```python
        entity.font_config = new_font_config
        self._edit_cmd.new_font_config = new_font_config
        self._edit_cmd.new_content = self.text_buffer
```

becomes:

```python
        entity.font_config = new_font_config
        self._edit_cmd.new_font_config = new_font_config
        self._edit_cmd.new_content = self.text_buffer
        if new_style is not None:
            entity.set_style(new_style)
            self._edit_cmd.new_style = new_style
```

If `Any` is not yet imported in this file, add it to the existing
`from typing import ...` line at the top.

- [ ] **Step 5: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/tools/test_text_box_tool.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_text_box.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/tools/text_box_tool.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/tools/test_text_box_tool.py
git commit -m "feat(sketcher): text transform controls in font properties"
```

---

### Task 6: Knock-out geometry and fill (Phase 3)

Executor tier: SONNET
Depends on: Task 4
Parallel-safe with: Task 3, 5, 8, 9, 12, 16, 18, 19, 20, 21

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py` (imports, `to_geometry`, new methods)
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/sketch.py:1823-1843` (`get_fill_render_data`)
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/renderer.py:300-318` (`_draw_text_box_fills`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_fill_methods.py`

**Interfaces:**

- Consumes: `TextBoxEntity._frame_glyphs(registry, text)` (Task 4);
`get_frame_polygon(registry)` (corners in order origin, width, fourth,
height); `rings_to_geometry(rings) -> Geometry` from
`SK/core/entities/polygon.py:94`; raygeo
`get_polygons_group_difference(subject, clip) -> list[Polygon]`,
`Geometry.to_polygons(tolerance)`, `Geometry.area()`,
`Matrix.transform_point((x, y)) -> (x, y)`.
- Produces:
  - `TextBoxEntity._rotation_matrix(registry) -> Matrix | None`
  - `TextBoxEntity.get_plate_ring(registry) -> list[tuple[float, float]] | None`
  (frame grown by `knockout_margin`, rotated with the text; `None` when
  knock-out is off or the frame is missing)
  - `TextBoxEntity.to_fill_geometry(registry, resolved_content=None) -> Geometry`
  (plate minus glyphs for knock-out, otherwise the same as `to_geometry`)
  - `TextBoxEntity.to_geometry` returns plate ring plus glyphs for knock-out.

- [ ] **Step 1: Write the failing tests**

Append to `SKT/core/entities/test_text_box_entity.py`:

```python
def test_knockout_stroke_contains_plate_ring(registry):
    box, width, height = _natural_box(
        registry, "HI", knockout=True, knockout_margin=2.0
    )
    assert box.to_geometry(registry).rect() == pytest.approx(
        (-2.0, -2.0, width + 2.0, height + 2.0), abs=1e-6
    )


def test_knockout_fill_is_plate_minus_glyphs(registry):
    plain, width, height = _natural_box(registry, "HI")
    box, _, _ = _natural_box(
        registry, "HI", knockout=True, knockout_margin=2.0
    )
    glyph_area = abs(plain.to_fill_geometry(registry).area())
    plate_area = (width + 4.0) * (height + 4.0)
    assert abs(box.to_fill_geometry(registry).area()) == pytest.approx(
        plate_area - glyph_area, rel=0.02
    )


def test_fill_geometry_without_knockout_equals_stroke(registry):
    box, _, _ = _natural_box(registry, "HI")
    assert box.to_fill_geometry(registry).rect() == pytest.approx(
        box.to_geometry(registry).rect()
    )


def test_knockout_plate_rotates_with_text(registry):
    box, width, height = _natural_box(
        registry, "HI", knockout=True, knockout_margin=2.0, rotation=90.0
    )
    min_x, min_y, max_x, max_y = box.to_geometry(registry).rect()
    assert max_x - min_x == pytest.approx(height + 4.0, abs=1e-6)
    assert max_y - min_y == pytest.approx(width + 4.0, abs=1e-6)
```

Append to `SKT/core/test_sketch_fill_methods.py`, and add
`from raygeo.geo.shape.text import FontConfig` to its imports:

```python
def test_get_fill_render_data_knockout_text(sketch):
    origin = sketch.add_point(0, 0)
    width_pt = sketch.add_point(20, 0)
    height_pt = sketch.add_point(0, 8)
    box = sketch.registry.get_entity(
        sketch.registry.add_text_box(
            origin, width_pt, height_pt, "HI", FontConfig()
        )
    )
    plain_rect = sketch.get_fill_render_data()[0].geometry.rect()

    box.set_style({"knockout": True, "knockout_margin": 2.0})
    knock_rect = sketch.get_fill_render_data()[0].geometry.rect()

    assert knock_rect[0] < plain_rect[0]
    assert knock_rect == pytest.approx((-2.0, -2.0, 22.0, 10.0), abs=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py -k knockout`
Expected: FAIL (`to_fill_geometry` does not exist; rect has no margin).

- [ ] **Step 3: Implement knock-out on the entity**

In `SK/core/entities/text_box.py` extend the imports:

```python
from raygeo.geo.shape.polygon import (
    get_polygons_group_difference,
    is_point_inside_polygon,
)
```

```python
from .polygon import rings_to_geometry
```

(`.polygon` only imports `.entity` and raygeo, so there is no import cycle.)

Refactor the rotation out of `_frame_glyphs` and add the plate helpers.
Replace the `_frame_glyphs` method from Task 4 with:

```python
    def _rotation_matrix(self, registry: "EntityRegistry") -> Matrix | None:
        """The rotation about the frame centre, or None when the text
        is not rotated."""
        if not self.rotation:
            return None
        p_width = registry.get_point(self.width_id)
        p_height = registry.get_point(self.height_id)
        centre = (
            (p_width.x + p_height.x) / 2.0,
            (p_width.y + p_height.y) / 2.0,
        )
        return Matrix.rotation(self.rotation, center=centre)

    def _frame_glyphs(
        self, registry: "EntityRegistry", text: str
    ) -> Geometry:
        """Maps the natural layout into the frame, then rotates it
        about the frame centre."""
        origin, pw, ph = self._build_frame_for_content(registry, text)
        geo, width, min_y, height = self._natural_layout(text)
        geo = geo.map_to_frame(
            origin,
            pw,
            ph,
            anchor_x=0.0,
            stable_src_width=width,
            anchor_y=min_y,
            stable_src_height=height,
        )
        rotation = self._rotation_matrix(registry)
        if rotation is not None:
            geo.transform(rotation)
        return geo

    def get_plate_ring(
        self, registry: "EntityRegistry"
    ) -> list[tuple[float, float]] | None:
        """The knock-out plate: the frame grown by the margin and
        rotated with the text. None when knock-out is off."""
        if not self.knockout:
            return None
        polygon = self.get_frame_polygon(registry)
        if polygon is None:
            return None
        (ox, oy), (wx, wy), _, (hx, hy) = polygon
        ux, uy = wx - ox, wy - oy
        vx, vy = hx - ox, hy - oy
        u_len = math.hypot(ux, uy) or 1.0
        v_len = math.hypot(vx, vy) or 1.0
        margin = self.knockout_margin
        ux, uy = ux / u_len * margin, uy / u_len * margin
        vx, vy = vx / v_len * margin, vy / v_len * margin
        signs = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ring = [
            (px + su * ux + sv * vx, py + su * uy + sv * vy)
            for (px, py), (su, sv) in zip(polygon, signs)
        ]
        rotation = self._rotation_matrix(registry)
        if rotation is not None:
            ring = [rotation.transform_point(point) for point in ring]
        return ring

    def to_fill_geometry(
        self,
        registry: "EntityRegistry",
        resolved_content: str | None = None,
    ) -> Geometry:
        """The area to fill: the glyphs, or for knock-out the plate
        with the glyphs cut out."""
        text = (
            resolved_content if resolved_content is not None else self.content
        )
        glyphs = self._frame_glyphs(registry, text)
        ring = self.get_plate_ring(registry)
        if ring is None:
            return glyphs
        return rings_to_geometry(
            get_polygons_group_difference([ring], glyphs.to_polygons(0.02))
        )
```

The existing `_build_frame_for_content` rescales the frame when resolved
content differs from `self.content`; `_rotation_matrix` and
`get_plate_ring` deliberately use the stored frame points, because the
plate is the frame the user sees.

Replace the body of `to_geometry` after its docstring with:

```python
        text = (
            resolved_content if resolved_content is not None else self.content
        )
        glyphs = self._frame_glyphs(registry, text)
        ring = self.get_plate_ring(registry)
        if ring is None:
            return glyphs
        plate = rings_to_geometry([ring])
        plate.extend(glyphs)
        return plate
```

- [ ] **Step 4: Route the fill consumers through `to_fill_geometry`**

In `SK/core/sketch.py`, in `get_fill_render_data`, replace

```python
                text_geo = entity.to_geometry(
                    self.registry, resolved_content=resolved
                )
```

with:

```python
                text_geo = entity.to_fill_geometry(
                    self.registry, resolved_content=resolved
                )
```

In `SK/ui_gtk/renderer.py`, in `_draw_text_box_fills`, replace

```python
                text_geo = entity.to_geometry(self.element.sketch.registry)
```

with:

```python
                text_geo = entity.to_fill_geometry(
                    self.element.sketch.registry
                )
```

- [ ] **Step 5: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_fill_methods.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_text_templates.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/sketch.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/renderer.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_fill_methods.py
git commit -m "feat(sketcher): knock-out text on a plate"
```

---

### Task 7: Knock-out rows in Font Properties (Phase 3)

Executor tier: ANTIGRAVITY-LOW
Depends on: Task 5, Task 6
Parallel-safe with: Task 8, 9, 10, 12, 16, 18, 19, 20, 21

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py`
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`

**Interfaces:**

- Consumes: `_add_switch_row`, `_get_style_from_ui`, `_update_style_ui`,
`_on_style_changed`, fixture `widget_with_box` (Task 5);
`LengthSpinRow(title, subtitle=None, **kwargs)` from
`rayforge.ui_gtk.shared.pref_rows` with `get_value_in_base_units()`,
`set_value_in_base_units(mm)` and a `value_changed` signal.
- Produces: widget attributes `knockout_switch`, `knockout_margin_row`;
style keys `knockout` and `knockout_margin` in `_get_style_from_ui`.

- [ ] **Step 1: Write the failing test**

Append to `SKT/ui_gtk/test_font_properties.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py -k knockout`
Expected: FAIL, no attribute `knockout_switch`.

- [ ] **Step 3: Add the rows**

In `SK/ui_gtk/font_properties.py` change the pref-row import to:

```python
from rayforge.ui_gtk.shared.pref_rows import (
    AngleSpinRow,
    LengthSpinRow,
    SpinRow,
)
```

In `_build_ui`, directly after `self.add(self.rotation_row)` add:

```python
        self.knockout_switch = self._add_switch_row(
            _("Knock-out"), self._on_style_changed
        )

        self.knockout_margin_row = LengthSpinRow(
            _("Knock-out Margin"),
            lower=0.0,
            upper=1000.0,
            value_in_base=2.0,
        )
        self.knockout_margin_row.value_changed.connect(
            self._on_style_changed
        )
        self.add(self.knockout_margin_row)
```

In `_update_style_ui`, inside the `try:` block after the
`upside_down_switch` line add:

```python
            self.knockout_switch.set_active(entity.knockout)
            self.knockout_margin_row.set_value_in_base_units(
                entity.knockout_margin
            )
```

In `_get_style_from_ui`, add two entries to the returned dict:

```python
            "knockout": self.knockout_switch.get_active(),
            "knockout_margin": (
                self.knockout_margin_row.get_value_in_base_units()
            ),
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py
git commit -m "feat(sketcher): knock-out controls in font properties"
```

---

### Task 8: Public path sampling helpers and circle paths (Phase 4)

Executor tier: SONNET
Depends on: none
Parallel-safe with: Task 1, 2, 3, 4, 5, 6, 7, 12, 16, 18, 19, 20, 21

**Files:**

- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/polyline.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/arrays/curve_along.py` (imports `:8`, `sample_path`, `_polyline_for` `:203`, `_cumulative_lengths`, `_point_at_arclength`, `path_length` `:318`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_curve_along_strategy.py`

**Interfaces:**

- Consumes: `Circle.center_idx`, `Circle.radius_pt_idx`
(`SK/core/entities/circle.py:23`).
- Produces:
  - `sketcher.core.polyline.cumulative_lengths(polyline: list[tuple[float, float]]) -> list[float]`
  - `sketcher.core.polyline.point_at_arclength(polyline, cum: list[float], s: float) -> tuple[tuple[float, float], tuple[float, float]]`
  (point, unit tangent)
  - `sketcher.core.arrays.curve_along.polyline_for(entity, registry) -> list[tuple[float, float]]`
  now also handling `Circle` (counter-clockwise from the radius point,
  closed: first point equals last point)
  - `cumulative_lengths` and `point_at_arclength` importable from
  `sketcher.core.arrays.curve_along` as well.
  - The private names `_polyline_for`, `_cumulative_lengths`,
  `_point_at_arclength` no longer exist (nothing else imports them).

`polyline.py` is a separate, dependency-free module because Task 9's helper
is imported by `entities/text_box.py`, and importing
`arrays.curve_along` from there would create an import cycle
(`arrays` imports `entities`).

- [ ] **Step 1: Update the tests first**

In `SKT/core/test_curve_along_strategy.py` replace the import block

```python
from sketcher.core.arrays.curve_along import (
    _cumulative_lengths,
    _point_at_arclength,
)
```

with:

```python
from sketcher.core.arrays.curve_along import (
    cumulative_lengths,
    path_length,
    point_at_arclength,
    polyline_for,
)
```

and rename every use of `_cumulative_lengths` to `cumulative_lengths` and
`_point_at_arclength` to `point_at_arclength` in that file (three tests:
`test_cumulative_lengths`, `test_point_at_arclength_interpolates`,
`test_point_at_arclength_clamps_to_end`). Then append:

```python
def test_polyline_for_circle_is_closed_and_on_radius():
    sketch = Sketch()
    c = sketch.registry.add_point(5.0, 5.0)
    r = sketch.registry.add_point(15.0, 5.0)
    circle_id = sketch.registry.add_circle(c, r)
    circle = sketch.registry.get_entity(circle_id)

    polyline = polyline_for(circle, sketch.registry)

    assert polyline[0] == pytest.approx((15.0, 5.0))
    assert polyline[-1] == pytest.approx(polyline[0])
    for x, y in polyline:
        assert math.hypot(x - 5.0, y - 5.0) == pytest.approx(10.0)
    assert polyline[1][1] > 5.0


def test_path_length_of_circle_is_circumference():
    sketch = Sketch()
    c = sketch.registry.add_point(0.0, 0.0)
    r = sketch.registry.add_point(10.0, 0.0)
    circle_id = sketch.registry.add_circle(c, r)

    assert path_length(sketch.registry, circle_id) == pytest.approx(
        2 * math.pi * 10.0, rel=1e-3
    )


def test_sample_circle_path_returns_points_on_circle():
    sketch = Sketch()
    c = sketch.registry.add_point(0.0, 0.0)
    r = sketch.registry.add_point(10.0, 0.0)
    circle_id = sketch.registry.add_circle(c, r)

    samples = sample_path(sketch.registry, circle_id, count=5)

    assert len(samples) == 5
    for (x, y), _angle in samples:
        assert math.hypot(x, y) == pytest.approx(10.0, rel=1e-3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_curve_along_strategy.py`
Expected: collection error, `cannot import name 'cumulative_lengths'`.

- [ ] **Step 3: Create `SK/core/polyline.py`**

Move the two pure helpers out of `curve_along.py` unchanged apart from
their names (keep the docstring and the "Binary search" comment):

```python
"""Arc-length helpers for polylines given as lists of (x, y) points."""

from __future__ import annotations

import math


def cumulative_lengths(
    polyline: list[tuple[float, float]],
) -> list[float]:
    cum = [0.0]
    for i in range(1, len(polyline)):
        dx = polyline[i][0] - polyline[i - 1][0]
        dy = polyline[i][1] - polyline[i - 1][1]
        cum.append(cum[-1] + math.hypot(dx, dy))
    return cum


def point_at_arclength(
    polyline: list[tuple[float, float]],
    cum: list[float],
    s: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Returns (point, unit_tangent) at arc length ``s`` along the path."""
    if s <= 0.0:
        dx = polyline[1][0] - polyline[0][0]
        dy = polyline[1][1] - polyline[0][1]
        n = math.hypot(dx, dy) or 1.0
        return polyline[0], (dx / n, dy / n)
    if s >= cum[-1]:
        a = polyline[-2]
        b = polyline[-1]
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        return b, (dx / n, dy / n)

    # Binary search for the segment containing s.
    lo, hi = 0, len(cum) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cum[mid] < s:
            lo = mid + 1
        else:
            hi = mid
    seg = max(1, lo)
    a = polyline[seg - 1]
    b = polyline[seg]
    seg_len = cum[seg] - cum[seg - 1]
    t = (s - cum[seg - 1]) / seg_len if seg_len > 0 else 0.0
    point = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    return point, (dx / n, dy / n)
```

- [ ] **Step 4: Update `SK/core/arrays/curve_along.py`**

1. Change the entity import (line 8) and add the polyline import below
 the `..entity_group` import:

```python
from ..entities import Arc, Bezier, Circle, Line
from ..entity_group import EntityGroup
from ..polyline import cumulative_lengths, point_at_arclength
```

2. Delete the function definitions `_cumulative_lengths` and
 `_point_at_arclength` from this file (they now live in `polyline.py`).
3. Rename `def _polyline_for(` to `def polyline_for(`.
4. In `sample_path` and `path_length`, rename the calls:
 `_polyline_for(` to `polyline_for(`, `_cumulative_lengths(` to
 `cumulative_lengths(`, `_point_at_arclength(` to `point_at_arclength(`.
 Check with:

```bash
grep -n "_polyline_for\|_cumulative_lengths\|_point_at_arclength" rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/arrays/curve_along.py
```

   Expected: no output.
5. In `polyline_for`, add a `Circle` branch directly before the final
   `return []`:

```python
    if isinstance(entity, Circle):
        c = p(entity.center_idx)
        start = p(entity.radius_pt_idx)
        radius = math.hypot(start[0] - c[0], start[1] - c[1])
        start_a = math.atan2(start[1] - c[1], start[0] - c[0])
        segments = 96
        return [
            (
                c[0] + radius * math.cos(start_a + 2 * math.pi * i / segments),
                c[1] + radius * math.sin(start_a + 2 * math.pi * i / segments),
            )
            for i in range(segments + 1)
        ]
```

6. In the class docstring of `CurveAlongArrayStrategy`, change
 `(a Line, Arc or Bezier)` to `(a Line, Arc, Circle or Bezier)`.

- [ ] **Step 5: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_curve_along_strategy.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/commands/test_curve_along_array_cmd.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_curve_array_drag.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/polyline.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/arrays/curve_along.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_curve_along_strategy.py
git commit -m "refactor(sketcher): public path sampling helpers with circle support"
```

---

### Task 9: `text_on_path` helper (Phase 4)

Executor tier: SONNET
Depends on: Task 8
Parallel-safe with: Task 1, 2, 3, 4, 5, 6, 7, 12, 16, 18, 19, 20, 21

**Files:**

- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/text_on_path.py`
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_on_path.py`

**Interfaces:**

- Consumes: `cumulative_lengths`, `point_at_arclength` from
`sketcher.core.polyline` (Task 8); raygeo `text_to_geometry`,
`FontConfig.get_text_position(text, index)`, `FontConfig.get_text_width`,
`Matrix.translation`, `Matrix.rotation(angle_deg)`, `Matrix @ Matrix`
(right-hand matrix applied first), `Geometry.is_empty()`.
- Produces:
`sketcher.core.text_on_path.text_on_path(text: str, font_config: FontConfig, polyline: list[tuple[float, float]], side: str = "outside", align: str = "center", offset: float = 0.0) -> Geometry`.
  - `"outside"`: glyphs sit on the left of the travel direction (upright
  when the path runs in +X). `"inside"`: the polyline is reversed, which
  flips both the normal and the reading direction.
  - `align` positions the text along the path (`"start"`, `"center"`,
  `"end"`); `offset` shifts it further along the path in mm.
  - A polyline whose first and last points coincide is closed: positions
  wrap. On an open path, positions beyond either end continue along the
  end tangent.
  - This module must not import `sketcher.core.entities` or
  `sketcher.core.arrays`.

- [ ] **Step 1: Write the failing tests**

Create `SKT/core/test_text_on_path.py`:

```python
import math

import pytest
from raygeo.geo.shape.text import FontConfig, text_to_geometry
from sketcher.core.text_on_path import text_on_path

FONT = FontConfig(family="sans-serif", size=10.0)
RADIUS = 50.0


def _clockwise_circle_from_bottom(radius=RADIUS, segments=96):
    """Closed circle about the origin, clockwise, starting at the
    bottom, so the middle of the path is the top."""
    return [
        (
            radius * math.cos(-math.pi / 2 - 2 * math.pi * i / segments),
            radius * math.sin(-math.pi / 2 - 2 * math.pi * i / segments),
        )
        for i in range(segments + 1)
    ]


def _radii(geo):
    return [
        math.hypot(x, y) for ring in geo.to_polygons(0.01) for x, y in ring
    ]


def test_ring_count_is_preserved():
    line = [(0.0, 0.0), (200.0, 0.0)]
    on_path = text_on_path("HELLO", FONT, line, align="start")
    plain = text_to_geometry("HELLO", font_config=FONT)
    assert len(on_path.to_polygons(0.01)) == len(plain.to_polygons(0.01))


def test_start_aligned_text_on_x_axis_matches_plain_layout():
    line = [(0.0, 0.0), (200.0, 0.0)]
    on_path = text_on_path("HELLO", FONT, line, align="start")
    plain = text_to_geometry("HELLO", font_config=FONT)
    assert on_path.rect() == pytest.approx(plain.rect(), abs=1e-3)


def test_outside_text_stays_outside_circle():
    geo = text_on_path("HHHHHHHHHH", FONT, _clockwise_circle_from_bottom())
    radii = _radii(geo)
    assert min(radii) >= RADIUS - 0.2
    assert max(radii) > RADIUS + 1.0


def test_inside_text_stays_inside_circle():
    geo = text_on_path(
        "HHHHHHHHHH", FONT, _clockwise_circle_from_bottom(), side="inside"
    )
    radii = _radii(geo)
    assert max(radii) <= RADIUS + 0.2
    assert min(radii) < RADIUS - 1.0


def test_centre_aligned_text_sits_at_top_of_circle():
    geo = text_on_path("HHHH", FONT, _clockwise_circle_from_bottom())
    min_x, min_y, max_x, _ = geo.rect()
    assert (min_x + max_x) / 2 == pytest.approx(0.0, abs=0.5)
    assert min_y > 0.0


def test_inside_centre_aligned_text_sits_at_bottom_of_circle():
    geo = text_on_path(
        "HHHH", FONT, _clockwise_circle_from_bottom(), "inside"
    )
    _, _, _, max_y = geo.rect()
    assert max_y < 0.0


def test_end_alignment_ends_at_path_end():
    line = [(0.0, 0.0), (200.0, 0.0)]
    geo = text_on_path("HELLO", FONT, line, align="end")
    width = FONT.get_text_width("HELLO")
    assert geo.rect()[0] >= 200.0 - width - 0.01
    assert geo.rect()[2] <= 200.0 + 0.01


def test_offset_shifts_along_path():
    line = [(0.0, 0.0), (200.0, 0.0)]
    base = text_on_path("HI", FONT, line, align="start")
    shifted = text_on_path("HI", FONT, line, align="start", offset=7.0)
    assert shifted.rect()[0] == pytest.approx(base.rect()[0] + 7.0)


def test_text_longer_than_open_path_extends_along_tangent():
    short = [(0.0, 0.0), (5.0, 0.0)]
    geo = text_on_path("HELLO WORLD", FONT, short, align="start")
    plain = text_to_geometry("HELLO WORLD", font_config=FONT)
    assert geo.rect() == pytest.approx(plain.rect(), abs=1e-3)


def test_blank_text_on_path_is_empty():
    line = [(0.0, 0.0), (10.0, 0.0)]
    assert text_on_path("   ", FONT, line).is_empty()
    assert text_on_path("", FONT, line).is_empty()


def test_degenerate_polyline_is_empty():
    assert text_on_path("HI", FONT, [(1.0, 1.0)]).is_empty()
    assert text_on_path("HI", FONT, [(1.0, 1.0), (1.0, 1.0)]).is_empty()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_on_path.py`
Expected: collection error, `No module named 'sketcher.core.text_on_path'`.

- [ ] **Step 3: Implement the helper**

Create `SK/core/text_on_path.py`:

```python
"""Lays text out along a polyline, one glyph at a time.

raygeo lays text out character by character without kerning or
shaping, so placing each character's outline at its advance position
on the path reproduces the straight layout exactly on a straight path.
"""

from __future__ import annotations

import math

from raygeo.geo import Geometry, Matrix
from raygeo.geo.shape.text import FontConfig, text_to_geometry

from .polyline import cumulative_lengths, point_at_arclength

Polyline = list[tuple[float, float]]


def _is_closed(polyline: Polyline) -> bool:
    (x0, y0), (x1, y1) = polyline[0], polyline[-1]
    return math.hypot(x1 - x0, y1 - y0) < 1e-6


def _start_position(
    align: str, total: float, width: float, offset: float
) -> float:
    if align == "start":
        return offset
    if align == "end":
        return total - width + offset
    return (total - width) / 2.0 + offset


def _locate(
    polyline: Polyline, cum: list[float], s: float, closed: bool
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Point and unit tangent at arc length ``s``. Closed paths wrap;
    open paths continue along their end tangent."""
    total = cum[-1]
    if closed:
        return point_at_arclength(polyline, cum, s % total)
    point, tangent = point_at_arclength(polyline, cum, s)
    overshoot = s - total if s > total else min(s, 0.0)
    return (
        (
            point[0] + tangent[0] * overshoot,
            point[1] + tangent[1] * overshoot,
        ),
        tangent,
    )


def text_on_path(
    text: str,
    font_config: FontConfig,
    polyline: Polyline,
    side: str = "outside",
    align: str = "center",
    offset: float = 0.0,
) -> Geometry:
    """
    Returns the glyph outlines of *text* laid along *polyline*.

    Each character sits at its advance position measured as arc
    length, rotated to the path tangent. "outside" places the glyphs
    on the left of the travel direction; "inside" reverses the path,
    which flips both the normal and the reading direction.
    """
    geo = Geometry()
    if len(polyline) < 2:
        return geo
    if side == "inside":
        polyline = polyline[::-1]
    cum = cumulative_lengths(polyline)
    total = cum[-1]
    if total <= 1e-9:
        return geo

    closed = _is_closed(polyline)
    start = _start_position(
        align, total, font_config.get_text_width(text), offset
    )
    for index, char in enumerate(text):
        glyph = text_to_geometry(char, font_config=font_config)
        if glyph.is_empty():
            continue
        advance = font_config.get_text_width(char)
        s = start + font_config.get_text_position(text, index) + advance / 2
        (px, py), (tx, ty) = _locate(polyline, cum, s, closed)
        glyph.transform(
            Matrix.translation(px, py)
            @ Matrix.rotation(math.degrees(math.atan2(ty, tx)))
            @ Matrix.translation(-advance / 2.0, 0.0)
        )
        geo.extend(glyph)
    return geo
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_on_path.py`
Expected: PASS.

If `test_outside_text_stays_outside_circle` fails with glyphs dipping
inside the circle away from the top, `Matrix.rotation` turns clockwise for
positive angles: negate the angle passed to `Matrix.rotation` in
`text_on_path` (only there) and re-run.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/text_on_path.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_on_path.py
git commit -m "feat(sketcher): lay text out along a path"
```

---

### Task 10: Bind a text box to a path; ring layout (Phase 4)

Executor tier: SONNET
Depends on: Task 6, Task 9
Parallel-safe with: Task 3, 5, 7, 8, 12, 16, 18, 19, 20, 21

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py` (imports, `geometry_signature`, `get_plate_ring`, `to_geometry`, `to_fill_geometry`, new methods)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`

**Interfaces:**

- Consumes: `text_on_path(text, font_config, polyline, side, align, offset)`
(Task 9); style attributes `path_entity_id`, `path_side`, `path_align`,
`path_offset`, `content_bottom` (Task 2); `_frame_glyphs`,
`get_plate_ring`, `to_fill_geometry` (Tasks 4 and 6);
`Entity.to_polyline(registry, tolerance) -> list[tuple[float, float]]`
(`SK/core/entities/entity.py:311`); `Entity.geometry_signature(registry)`.
- Produces:
  - `TextBoxEntity.get_path_polyline(registry) -> list[tuple[float, float]] | None`
  (`None` when unbound, the entity is gone, or it is not a line, arc,
  circle or Bezier). A circle is sampled clockwise starting at its
  bottom, so centred text sits on top.
  - `TextBoxEntity._glyphs(registry, text) -> Geometry`: path layout when
  bound, frame layout otherwise.
  - Path-bound text honours `reverse`, `path_side`, `path_align`,
  `path_offset` and, on a circle, `content_bottom`. It ignores `mirrored`,
  `vertical`, `rotation` and `knockout`, and uses the natural font size
  instead of the frame.
  - `get_point_ids()` is unchanged: path points are not text box points.

- [ ] **Step 1: Write the failing tests**

Append to `SKT/core/entities/test_text_box_entity.py`, and add `import math`
at the top of the file:

```python
def _box_on_circle(registry, content="HHHH", radius=50.0, **style):
    centre = registry.add_point(0.0, 0.0)
    rim = registry.add_point(radius, 0.0)
    circle_id = registry.add_circle(centre, rim)
    box, _, _ = _natural_box(registry, content)
    box.set_style({"path_entity_id": circle_id, **style})
    return box, circle_id


def _ring_radii(geo):
    return [
        math.hypot(x, y) for ring in geo.to_polygons(0.01) for x, y in ring
    ]


def test_text_on_circle_sits_on_top_outside(registry):
    box, _ = _box_on_circle(registry)
    geo = box.to_geometry(registry)
    min_x, min_y, max_x, _ = geo.rect()
    assert min(_ring_radii(geo)) >= 50.0 - 0.2
    assert (min_x + max_x) / 2 == pytest.approx(0.0, abs=0.5)
    assert min_y > 0.0


def test_inside_text_on_circle_sits_at_bottom_inside(registry):
    box, _ = _box_on_circle(registry, path_side="inside")
    geo = box.to_geometry(registry)
    assert max(_ring_radii(geo)) <= 50.0 + 0.2
    assert geo.rect()[3] < 0.0


def test_ring_layout_has_top_and_bottom_text(registry):
    box, _ = _box_on_circle(registry, content_bottom="HHHH")
    top_only, _ = _box_on_circle(registry)
    geo = box.to_geometry(registry)
    rings = len(geo.to_polygons(0.01))
    assert rings == 2 * len(top_only.to_geometry(registry).to_polygons(0.01))
    _, min_y, _, max_y = geo.rect()
    assert max_y > 50.0
    assert min_y < 0.0
    assert min_y > -50.0 - 0.2


def test_text_follows_line_from_its_first_point(registry):
    p1 = registry.add_point(0.0, 100.0)
    p2 = registry.add_point(200.0, 100.0)
    line_id = registry.add_line(p1, p2)
    box, _, _ = _natural_box(registry, "HI")
    box.set_style({"path_entity_id": line_id, "path_align": "start"})
    min_x, min_y, _, _ = box.to_geometry(registry).rect()
    assert min_x < 5.0
    assert min_y >= 100.0 - 0.01


def test_text_follows_arc_from_its_start_point(registry):
    centre = registry.add_point(0.0, 0.0)
    start = registry.add_point(50.0, 0.0)
    end = registry.add_point(0.0, 50.0)
    arc_id = registry.add_arc(start, end, centre, cw=False)
    box, _, _ = _natural_box(registry, "H")
    box.set_style({"path_entity_id": arc_id, "path_align": "start"})
    min_x, min_y, max_x, max_y = box.to_geometry(registry).rect()
    centre_x, centre_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    assert math.hypot(centre_x - 50.0, centre_y) < math.hypot(
        centre_x, centre_y - 50.0
    )


def test_missing_path_entity_falls_back_to_frame(registry):
    plain, _, _ = _natural_box(registry, "HI")
    bound, _, _ = _natural_box(registry, "HI")
    bound.set_style({"path_entity_id": 987654})
    assert bound.get_path_polyline(registry) is None
    assert bound.to_geometry(registry).rect() == pytest.approx(
        plain.to_geometry(registry).rect()
    )


def test_text_box_cannot_be_its_own_kind_of_path(registry):
    other, _, _ = _natural_box(registry, "PATH")
    bound, _, _ = _natural_box(registry, "HI")
    bound.set_style({"path_entity_id": other.id})
    assert bound.get_path_polyline(registry) is None


def test_moving_the_path_changes_the_signature(registry):
    box, circle_id = _box_on_circle(registry)
    before = box.geometry_signature(registry)
    circle = registry.get_entity(circle_id)
    registry.get_point(circle.radius_pt_idx).x = 60.0
    assert box.geometry_signature(registry) != before


def test_path_points_are_not_text_box_points(registry):
    box, circle_id = _box_on_circle(registry)
    circle = registry.get_entity(circle_id)
    assert circle.center_idx not in box.get_point_ids()


def test_knockout_is_ignored_on_a_path(registry):
    box, _ = _box_on_circle(registry, knockout=True)
    assert box.get_plate_ring(registry) is None
    assert box.to_fill_geometry(registry).rect() == pytest.approx(
        box.to_geometry(registry).rect()
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py -k "circle or path or ring or line or arc"`
Expected: FAIL (`get_path_polyline` does not exist; text ignores the path).

- [ ] **Step 3: Implement the path binding**

In `SK/core/entities/text_box.py` extend the imports:

```python
from ..text_on_path import text_on_path
from ..types import EntityID
from .arc import Arc
from .bezier import Bezier
from .circle import Circle
from .entity import Entity
from .line import Line
from .polygon import rings_to_geometry
```

(`..text_on_path` imports only raygeo and `..polyline`; the sibling entity
modules are already loaded by `entities/__init__.py` before `text_box`.)

After `_STYLE_CHOICES` add:

```python
_PATH_ENTITY_TYPES = (Line, Arc, Circle, Bezier)
_PATH_TOLERANCE = 0.02
_CIRCLE_SEGMENTS = 96
```

Add these methods after `_frame_glyphs`:

```python
    def _circle_polyline(
        self, circle: Circle, registry: "EntityRegistry"
    ) -> list[tuple[float, float]]:
        """Clockwise from the bottom, so centred text sits on top and
        reads left to right."""
        centre = registry.get_point(circle.center_idx)
        radius = circle.radius(registry)
        return [
            (
                centre.x
                + radius
                * math.cos(-math.pi / 2 - 2 * math.pi * i / _CIRCLE_SEGMENTS),
                centre.y
                + radius
                * math.sin(-math.pi / 2 - 2 * math.pi * i / _CIRCLE_SEGMENTS),
            )
            for i in range(_CIRCLE_SEGMENTS + 1)
        ]

    def get_path_polyline(
        self, registry: "EntityRegistry"
    ) -> list[tuple[float, float]] | None:
        """The polyline the text follows, or None when the text box is
        not bound to a usable path entity."""
        if self.path_entity_id is None:
            return None
        entity = registry.get_entity(self.path_entity_id)
        if not isinstance(entity, _PATH_ENTITY_TYPES):
            return None
        if isinstance(entity, Circle):
            polyline = self._circle_polyline(entity, registry)
        elif isinstance(entity, Line):
            p1 = registry.get_point(entity.p1_idx)
            p2 = registry.get_point(entity.p2_idx)
            polyline = [(p1.x, p1.y), (p2.x, p2.y)]
        else:
            polyline = list(entity.to_polyline(registry, _PATH_TOLERANCE))
        return polyline if len(polyline) >= 2 else None

    def _path_glyphs(
        self,
        registry: "EntityRegistry",
        text: str,
        polyline: list[tuple[float, float]],
    ) -> Geometry:
        if self.reverse:
            text = text[::-1]
        geo = text_on_path(
            text,
            self.font_config,
            polyline,
            self.path_side,
            self.path_align,
            self.path_offset,
        )
        path_entity = registry.get_entity(self.path_entity_id)
        if self.content_bottom and isinstance(path_entity, Circle):
            geo.extend(
                text_on_path(
                    self.content_bottom,
                    self.font_config,
                    polyline[::-1],
                    "outside",
                    "center",
                    -self.path_offset,
                )
            )
        return geo

    def _glyphs(self, registry: "EntityRegistry", text: str) -> Geometry:
        """Glyph outlines on the bound path, or in the frame when the
        text box follows no path."""
        polyline = self.get_path_polyline(registry)
        if polyline is None:
            return self._frame_glyphs(registry, text)
        return self._path_glyphs(registry, text, polyline)
```

Notes for the implementer:

- The circle polyline runs clockwise from the bottom. Its reverse runs
counter-clockwise from the bottom, so text centred on it sits at the
bottom with its ascenders pointing at the centre: upright, inside the
circle. That is why the bottom string uses `polyline[::-1]` with side
`"outside"`, and why `path_side="inside"` on a circle lands at the bottom.
- `registry.get_entity(None)` is never reached: `_path_glyphs` is only
called when `get_path_polyline` returned a polyline.

In `get_plate_ring`, change the first guard to:

```python
        if not self.knockout or self.get_path_polyline(registry) is not None:
            return None
```

In both `to_geometry` and `to_fill_geometry`, replace

```python
        glyphs = self._frame_glyphs(registry, text)
```

with:

```python
        glyphs = self._glyphs(registry, text)
```

In `geometry_signature`, extend the returned tuple so a moved path is
noticed. Replace the method body after its docstring with:

```python
        font = self.font_config
        path_entity = (
            registry.get_entity(self.path_entity_id)
            if self.path_entity_id is not None
            else None
        )
        path_signature = (
            path_entity.geometry_signature(registry)
            if isinstance(path_entity, _PATH_ENTITY_TYPES)
            else ()
        )
        return (
            super().geometry_signature(registry)
            + (
                self.content,
                font.family,
                font.size,
                font.bold,
                font.italic,
            )
            + tuple(self.get_style().values())
            + path_signature
        )
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_on_path.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_fill_methods.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_array_text_template.py`
Expected: PASS.

If `test_text_follows_arc_from_its_start_point` fails, `Entity.to_polyline`
returns arcs end-first: in `get_path_polyline`, reverse the polyline in the
`else` branch when its first point is farther from the arc's start point
than its last point, using `registry.get_point(entity.start_idx)` (both
`Arc` and `Bezier` have `start_idx`).

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/entities/text_box.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py
git commit -m "feat(sketcher): text boxes follow a path, with ring layout"
```

---

### Task 11: Path controls in Font Properties (Phase 4)

Executor tier: SONNET
Depends on: Task 7, Task 10
Parallel-safe with: Task 8, 9, 12, 16, 18, 19, 20, 21

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/studio.py:499-516` (`_on_selection_changed`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`

**Interfaces:**

- Consumes: Task 5 widget plumbing and fixture; style keys
`path_entity_id`, `path_side`, `path_align`, `path_offset`,
`content_bottom` (Task 2); `LengthSpinRow` (import added in Task 7).
- Produces:
  - `sketcher.ui_gtk.font_properties.split_text_selection(registry, entity_ids) -> tuple[int | None, int | None]`
  returning `(text_box_id, path_candidate_id)`: a text box id when the
  selection is exactly one text box, optionally plus exactly one line,
  arc, circle or Bezier.
  - `FontPropertiesWidget.set_text_entity(entity_id, path_candidate_id: int | None = None)`
  - widget attributes `follow_path_row`, `path_side_row`, `path_align_row`,
  `path_offset_row`, `bottom_text_row`.
- User flow: select the text box and one line, arc, circle or Bezier
together; the panel shows **Follow Path**; activating it binds the text.
Activating it with only the text box selected releases the binding.

- [ ] **Step 1: Write the failing tests**

Append to `SKT/ui_gtk/test_font_properties.py`, and add
`from sketcher.ui_gtk.font_properties import split_text_selection` to the
imports:

```python
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
    assert split_text_selection(
        registry, [tb_id, line_id, other_line]
    ) == (None, None)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py -k "path or split"`
Expected: collection error, `cannot import name 'split_text_selection'`.

- [ ] **Step 3: Add the selection helper and the rows**

In `SK/ui_gtk/font_properties.py` add to the imports:

```python
from ..core.entities import Arc, Bezier, Circle, Line
```

After `logger = logging.getLogger(__name__)` add:

```python
_PATH_SIDES = ("outside", "inside")
_PATH_ALIGNS = ("start", "center", "end")


def split_text_selection(
    registry, entity_ids
) -> tuple[int | None, int | None]:
    """
    Splits a selection into (text box id, path candidate id).

    A text box id is returned when the selection is exactly one text
    box, optionally together with exactly one line, arc, circle or
    bezier the text could follow.
    """
    text_ids = []
    path_ids = []
    for entity_id in entity_ids:
        entity = registry.get_entity(entity_id)
        if isinstance(entity, TextBoxEntity):
            text_ids.append(entity_id)
        elif isinstance(entity, (Line, Arc, Circle, Bezier)):
            path_ids.append(entity_id)
        else:
            return None, None
    if len(text_ids) != 1 or len(path_ids) > 1:
        return None, None
    return text_ids[0], path_ids[0] if path_ids else None
```

In `__init__`, after `self._current_font_family = "sans-serif"` add:

```python
        self._path_candidate_id: int | None = None
        self._path_entity_id: int | None = None
```

In `_build_ui`, directly after `self.add(self.knockout_margin_row)` add:

```python
        self.follow_path_row = Adw.ActionRow()
        self.follow_path_row.set_title(_("Follow Path"))
        self.follow_path_row.set_activatable(True)
        self.follow_path_row.connect(
            "activated", self._on_follow_path_activated
        )
        self.add(self.follow_path_row)

        self.path_side_row = Adw.ComboRow()
        self.path_side_row.set_title(_("Path Side"))
        self.path_side_row.set_model(
            Gtk.StringList.new([_("Outside"), _("Inside")])
        )
        self.path_side_row.connect("notify::selected", self._on_style_changed)
        self.add(self.path_side_row)

        self.path_align_row = Adw.ComboRow()
        self.path_align_row.set_title(_("Path Alignment"))
        self.path_align_row.set_model(
            Gtk.StringList.new([_("Start"), _("Center"), _("End")])
        )
        self.path_align_row.connect(
            "notify::selected", self._on_style_changed
        )
        self.add(self.path_align_row)

        self.path_offset_row = LengthSpinRow(
            _("Path Offset"),
            lower=-10000.0,
            upper=10000.0,
            value_in_base=0.0,
        )
        self.path_offset_row.value_changed.connect(self._on_style_changed)
        self.add(self.path_offset_row)

        self.bottom_text_row = Adw.EntryRow()
        self.bottom_text_row.set_title(_("Bottom Text"))
        self.bottom_text_row.set_show_apply_button(True)
        self.bottom_text_row.connect("apply", self._on_style_changed)
        self.add(self.bottom_text_row)
```

Change the signature and the start of `set_text_entity` to:

```python
    def set_text_entity(
        self, entity_id: int | None, path_candidate_id: int | None = None
    ):
        """
        Sets the text entity to display font properties for.
        Hides the widget if entity_id is None. *path_candidate_id* is
        a selected line, arc, circle or bezier the text could follow.
        """
        self._text_entity_id = entity_id
        self._path_candidate_id = path_candidate_id
```

(the rest of the method is unchanged).

In `_update_style_ui`, inside the `try:` block after the
`knockout_margin_row` lines add:

```python
            self._path_entity_id = entity.path_entity_id
            self.path_side_row.set_selected(
                _PATH_SIDES.index(entity.path_side)
            )
            self.path_align_row.set_selected(
                _PATH_ALIGNS.index(entity.path_align)
            )
            self.path_offset_row.set_value_in_base_units(entity.path_offset)
            self.bottom_text_row.set_text(entity.content_bottom)
            self._update_follow_path_subtitle()
```

In `_get_style_from_ui`, add to the returned dict:

```python
            "path_entity_id": self._path_entity_id,
            "path_side": _PATH_SIDES[self.path_side_row.get_selected()],
            "path_align": _PATH_ALIGNS[self.path_align_row.get_selected()],
            "path_offset": self.path_offset_row.get_value_in_base_units(),
            "content_bottom": self.bottom_text_row.get_text(),
```

After `_on_upside_down_changed` add:

```python
    def _update_follow_path_subtitle(self):
        """Explains what activating the follow-path row will do."""
        if self._path_candidate_id is not None:
            subtitle = _("Bind the text to the selected shape")
        elif self._path_entity_id is not None:
            subtitle = _("Following a path. Activate to release")
        else:
            subtitle = _(
                "Select the text box together with a line, arc, "
                "circle or curve"
            )
        self.follow_path_row.set_subtitle(subtitle)

    def _on_follow_path_activated(self, row, *args):
        """Binds the text to the selected shape, or releases it."""
        if self._in_update or self._text_entity_id is None:
            return
        self._path_entity_id = self._path_candidate_id
        self._update_follow_path_subtitle()
        self._apply_font_config()
```

- [ ] **Step 4: Pass the path candidate from the studio**

In `SK/ui_gtk/studio.py`, add `split_text_selection` to the existing import
of `FontPropertiesWidget`:

```python
from .font_properties import FontPropertiesWidget, split_text_selection
```

(keep the module path the file already uses for `FontPropertiesWidget`),
and in `_on_selection_changed` replace

```python
        text_entity_id = None
        if len(selection.entity_ids) == 1:
            entity_id = selection.entity_ids[0]
            entity = self.canvas.sketch_element.sketch.registry.get_entity(
                entity_id
            )
            if isinstance(entity, TextBoxEntity):
                text_entity_id = entity_id

        self.font_properties.set_text_entity(text_entity_id)
        self._update_status_bar()
```

with:

```python
        text_entity_id, path_candidate_id = split_text_selection(
            self.canvas.sketch_element.sketch.registry,
            selection.entity_ids,
        )

        self.font_properties.set_text_entity(
            text_entity_id, path_candidate_id
        )
        self._update_status_bar()
```

If `TextBoxEntity` is then unused in `studio.py`, remove its import
(pyflakes reports it).

- [ ] **Step 5: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/studio.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py
git commit -m "feat(sketcher): path controls for text boxes"
```

---

### Task 12: raygeo `load_font_file` (Phase 5, EXTERNAL REPOSITORY)

> **This task is not in the Rayforge worktree.** It is a pull request
> against `https://github.com/barebaric/raygeo` and must be done in a
> separate checkout of that repository. Do not edit any Rayforge file in
> this task. Tasks 13, 14 and 15 are blocked until the checkpoint at the
> end of this task is passed.

Executor tier: SONNET
Depends on: none
Parallel-safe with: every Rayforge task (different repository)

**Files (in the raygeo repository, at tag `v1.63.0` or newer `main`):**

- Modify: `src/geo/shape/text.rs` (`font_database` `:92`, `cached_font_data`, `find_face_id` `:173`, new `load_font_file`)
- Modify: `src/python/geo/shape/text.rs` (import list `:7`, `register` `:14`, new binding)
- Regenerate: `python/raygeo/geo/shape/text/__init__.pyi` (only via `make stubs`)
- Create: `tests/assets/fonts/TestFont-Regular.ttf` (an OFL-licensed font; copy `DejaVuSans.ttf` renamed is not acceptable because its family name is already a system font; use a font whose family name is unlikely to be installed, for example `Bungee-Regular.ttf` from Google Fonts under the SIL OFL, and add its `OFL.txt` next to it)
- Test: `tests/geo/shape/test_geo_shape_text.py`

**Interfaces:**

- Consumes: `fontdb::Database::load_font_file`, `Database::faces`.
- Produces (Python): `raygeo.geo.shape.text.load_font_file(path: str) -> list[str]`
returning the family names of the faces the file added (deduplicated,
in face order). Raises `OSError` when the file cannot be read and
`ValueError` when it contains no font face. After a successful call,
`FontConfig(family=<name>)` resolves to the loaded face in the same
process.

raygeo repository rules (its `AGENTS.md`): never edit `.pyi` stubs or
markdown docs by hand (`make stubs`, `make docs`); never add Rust
`#[test]` blocks, all tests are Python under `tests/`; use the `make`
targets; run `make dev` before `make test`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/geo/shape/test_geo_shape_text.py`, and change its import
line to
`from raygeo.geo.shape.text import FontConfig, load_font_file, text_to_geometry`
plus `from pathlib import Path` and `import pytest`:

```python
FONT_FILE = (
    Path(__file__).parents[2] / "assets" / "fonts" / "TestFont-Regular.ttf"
)


def test_load_font_file_returns_family_names():
    families = load_font_file(str(FONT_FILE))
    assert families
    assert all(isinstance(name, str) and name for name in families)


def test_loaded_font_is_used_for_layout():
    family = load_font_file(str(FONT_FILE))[0]
    custom = text_to_geometry("Hg", font_config=FontConfig(family=family))
    fallback = text_to_geometry(
        "Hg", font_config=FontConfig(family="sans-serif")
    )
    assert len(custom.data) > 0
    assert custom.rect() != fallback.rect()


def test_load_font_file_twice_is_harmless():
    first = load_font_file(str(FONT_FILE))
    second = load_font_file(str(FONT_FILE))
    assert first == second


def test_load_font_file_missing_path_raises(tmp_path):
    with pytest.raises(OSError):
        load_font_file(str(tmp_path / "missing.ttf"))


def test_load_font_file_rejects_non_font(tmp_path):
    bogus = tmp_path / "bogus.ttf"
    bogus.write_bytes(b"this is not a font")
    with pytest.raises(ValueError):
        load_font_file(str(bogus))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `make dev && python -m pytest tests/geo/shape/test_geo_shape_text.py -v`
Expected: collection error, `cannot import name 'load_font_file'`.

- [ ] **Step 3: Make the font database writable**

In `src/geo/shape/text.rs` change the sync import to:

```rust
use std::sync::{Mutex, OnceLock, RwLock};
```

Replace `font_database` so it returns the lock instead of a shared
reference (keep the doc comment and the DejaVu preference block exactly as
they are, only the signature, the static and the final expression change):

```rust
fn font_database() -> &'static RwLock<fontdb::Database> {
    static DB: OnceLock<RwLock<fontdb::Database>> = OnceLock::new();
    DB.get_or_init(|| {
        let mut db = fontdb::Database::new();
        db.load_system_fonts();

        // (existing DejaVu Sans / DejaVu Serif preference block, unchanged)

        RwLock::new(db)
    })
}
```

In `cached_font_data`, replace `let db = font_database();` with:

```rust
    let db = font_database().read().unwrap();
```

In `find_face_id`, replace `let db = font_database();` with:

```rust
    let db = font_database().read().unwrap();
```

Add the loader below `find_face_id`:

```rust
/// Error returned by [`load_font_file`].
#[derive(Debug)]
pub enum FontLoadError {
    /// The file could not be read.
    Io(std::io::Error),
    /// The file was read but contains no usable font face.
    NoFaces,
}

/// Load a font file into the process-wide font database.
///
/// Returns the family names of the faces the file added, deduplicated
/// and in face order. Loading the same file again adds the faces again;
/// family lookup keeps resolving to a matching face, so this is
/// harmless.
pub fn load_font_file(
    path: &std::path::Path,
) -> Result<Vec<String>, FontLoadError> {
    let mut db = font_database().write().unwrap();
    let known: std::collections::HashSet<fontdb::ID> =
        db.faces().map(|face| face.id).collect();
    db.load_font_file(path).map_err(FontLoadError::Io)?;

    let mut families: Vec<String> = Vec::new();
    for face in db.faces().filter(|face| !known.contains(&face.id)) {
        for (name, _) in &face.families {
            if !families.contains(name) {
                families.push(name.clone());
            }
        }
    }
    if families.is_empty() {
        return Err(FontLoadError::NoFaces);
    }
    Ok(families)
}
```

- [ ] **Step 4: Add the Python binding**

In `src/python/geo/shape/text.rs`, add `load_font_file` and `FontLoadError`
to the `use crate::geo::shape::text::{...}` list, add
`use pyo3::exceptions::{PyOSError, PyValueError};`, register the function
in `register` next to `text_to_geometry_py`:

```rust
    m.add_function(wrap_pyfunction!(load_font_file_py, &m)?)?;
```

and add the function at the end of the file:

```rust
/// Load a font file (.ttf, .otf, .ttc) into the font database and
/// return the family names it provides.
#[gen_stub_pyfunction(module = "raygeo.geo.shape.text")]
#[pyfunction(name = "load_font_file")]
fn load_font_file_py(path: &str) -> PyResult<Vec<String>> {
    match load_font_file(std::path::Path::new(path)) {
        Ok(families) => Ok(families),
        Err(FontLoadError::Io(err)) => {
            Err(PyOSError::new_err(format!("{path}: {err}")))
        }
        Err(FontLoadError::NoFaces) => Err(PyValueError::new_err(format!(
            "{path}: no font face found"
        ))),
    }
}
```

- [ ] **Step 5: Regenerate stubs and docs, lint, test**

Run: `make dev && make stubs && make docs && make format && make lint`
Expected: no errors; `python/raygeo/geo/shape/text/__init__.pyi` now lists
`load_font_file` in `__all__`.
Run: `python -m pytest tests/geo/shape/test_geo_shape_text.py -v`
Expected: PASS.
Run: `make test`
Expected: PASS.

- [ ] **Step 6: Confirm the swash licence (spec open item)**

Run: `cargo metadata --format-version 1 | python3 -c "import json,sys; print([p['license'] for p in json.load(sys.stdin)['packages'] if p['name']=='swash'])"`
Expected: a licence compatible with MIT (the analysis expects
`Apache-2.0 OR MIT`). Put the printed value in the PR description. If it
is anything else, stop and escalate to the coordinator.

- [ ] **Step 7: Commit and open the PR**

```bash
git checkout -b feat/load-font-file
git add src/geo/shape/text.rs src/python/geo/shape/text.rs python/raygeo/geo/shape/text/__init__.pyi docs tests/geo/shape/test_geo_shape_text.py tests/assets/fonts
git commit -m "feat(text): load font files into the font database"
git push -u origin feat/load-font-file
gh pr create --title "feat(text): load_font_file" --body "Adds raygeo.geo.shape.text.load_font_file(path) -> list[str] so Rayforge can use user-installed fonts. font_database() becomes an RwLock; reads take the read lock."
```

Opening the PR is an outward-facing action: do it only when the
coordinator has approved it.

- [ ] **Step 8: EXTERNAL-PR CHECKPOINT (blocks Tasks 13, 14, 15)**

Report the PR URL to the coordinator and stop. The checkpoint is passed
only when all three are true:

1. the PR is merged,
2. a raygeo release containing it is published on PyPI,
3. the coordinator has recorded the released version number (called
 `<RAYGEO_VERSION>` in Task 13).

Until then Tasks 13 to 15 must not start. To develop them early against
the unreleased code, use the local override from
`docs/agents/raygeo.md`: `ln -s /path/to/raygeo external/raygeo`, then
`scripts/pixi-raygeo.sh run test <path>`; nothing produced that way may be
committed with a version pin.

---

### Task 13: Bump the raygeo pin (Phase 5)

Executor tier: ANTIGRAVITY-LOW
Depends on: Task 12 (checkpoint passed, `<RAYGEO_VERSION>` known)
Parallel-safe with: Task 16, 17, 18, 19, 20, 21, 22

**Files:**

- Modify: `requirements.txt:2`
- Modify: `pixi.toml:41`
- Modify: `pixi.lock` (regenerated by pixi, never by hand)

**Interfaces:**

- Consumes: the released raygeo version number from the Task 12 checkpoint.
- Produces: `from raygeo.geo.shape.text import load_font_file` works in the
pixi environment.

`<RAYGEO_VERSION>` below is not a placeholder to invent: it is the exact
version string the coordinator recorded at the Task 12 checkpoint (for
example `1.64.0`). If you do not have it, stop and ask the coordinator.

- [ ] **Step 1: Write the failing check**

Run: `pixi run python -c "from raygeo.geo.shape.text import load_font_file"`
Expected: `ImportError: cannot import name 'load_font_file'`.

- [ ] **Step 2: Bump the pins**

In `requirements.txt` change line 2 from `raygeo==1.63.0` to
`raygeo==<RAYGEO_VERSION>`.
In `pixi.toml` change line 41 from `raygeo = "==1.63.0"` to
`raygeo = "==<RAYGEO_VERSION>"`.
`debian/control` does not pin raygeo (verified: no match), so it needs no
change.

- [ ] **Step 3: Refresh the lock file and verify**

Run: `pixi install`
Expected: `pixi.lock` updated, raygeo `<RAYGEO_VERSION>` installed.
Run: `pixi run python -c "from raygeo.geo.shape.text import load_font_file; print(load_font_file)"`
Expected: prints a built-in function.
Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/entities/test_text_box_entity.py`
Expected: PASS (text layout unchanged by the new raygeo).

- [ ] **Step 4: Commit**

```bash
git add requirements.txt pixi.toml pixi.lock
git commit -m "chore: bump raygeo for load_font_file"
```

---

### Task 14: Custom font storage and loading (Phase 5)

Executor tier: SONNET
Depends on: Task 13
Parallel-safe with: Task 16, 17, 18, 19, 20, 21, 22

**Files:**

- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/fonts.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/worker.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/frontend.py`
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py`
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/assets/TestFont-Regular.ttf` and `OFL.txt` (the same OFL font and licence file added to raygeo in Task 12)

**Interfaces:**

- Consumes: `raygeo.geo.shape.text.load_font_file(path: str) -> list[str]`
(raises `OSError` / `ValueError`); `rayforge.config.get_addon_data_dir(name) -> Path`
(`rayforge/config.py:36`, creates the directory).
- Produces (in `sketcher.core.fonts`):
  - `fonts_dir() -> Path` (`get_addon_data_dir("sketcher") / "fonts"`, created)
  - `install_font(src: Path) -> list[str]` (family names; raises
  `ValueError` for a wrong extension or a file raygeo cannot parse)
  - `remove_font(family: str) -> None`
  - `load_installed_fonts() -> None` (idempotent per file)
  - `list_custom_families() -> list[str]` (sorted)
  - `is_custom_family(family: str) -> bool`

Fonts are loaded in three places because job geometry is rebuilt outside
the UI process: `rayforge_init` in `worker.py` and `frontend.py` (as the
spec says), and `register_asset_types` in `worker.py`. The last one is
the hook that is certain to run in any process able to deserialize a
`Sketch`; whether pipeline subprocesses call `rayforge_init` could not be
confirmed (spec open item). Loading is idempotent, so the overlap is free.

- [ ] **Step 1: Write the failing tests**

Create `SKT/core/test_fonts.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py`
Expected: collection error, `cannot import name 'fonts'`.

- [ ] **Step 3: Implement `SK/core/fonts.py`**

```python
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
```

- [ ] **Step 4: Load the fonts in every process**

In `SK/worker.py` add below the existing `hookimpl` import:

```python
from .core.fonts import load_installed_fonts
```

add a new hook after `ADDON_NAME = "sketcher"`:

```python
@hookimpl
def rayforge_init(context):
    """Load user-installed fonts so job geometry uses the same faces."""
    load_installed_fonts()
```

and call the loader as the first statement of the existing
`register_asset_types` hook, before its lazy `Sketch` import:

```python
    load_installed_fonts()
```

In `SK/frontend.py` add below the existing `hookimpl` import:

```python
from .core.fonts import load_installed_fonts
```

and add after `ADDON_NAME = "sketcher"`:

```python
@hookimpl
def rayforge_init(context):
    """Load user-installed fonts for the canvas."""
    load_installed_fonts()
```

- [ ] **Step 5: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/test_sketcher_workpiece.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/fonts.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/worker.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/frontend.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/assets/TestFont-Regular.ttf rayforge/builtin_addons/rayforge-addon-sketcher/tests/assets/OFL.txt
git commit -m "feat(sketcher): install and load custom fonts"
```

---

### Task 15: Custom font list and missing-font warning (Phase 5)

Executor tier: SONNET
Depends on: Task 11, Task 14
Parallel-safe with: Task 16, 18, 19, 20, 21

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/fonts.py` (add `is_known_family`)
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py`
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py`
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`

**Interfaces:**

- Consumes: `install_font`, `remove_font`, `list_custom_families`,
`is_custom_family` (Task 14); Task 5 widget plumbing and fixture;
`Gtk.FileDialog` (pattern: `rayforge/ui_gtk/machine/profile_importer.py:48`).
- Produces:
  - `sketcher.core.fonts.is_known_family(family: str, system_families: Iterable[str]) -> bool`
  - widget attributes `custom_font_row` (`Adw.ComboRow`),
  `install_font_row`, `remove_font_row`, `missing_font_row`
  - `FontPropertiesWidget._install_font_file(path: Path) -> None`
- The system font row (`font_family_row`) stays as it is. The separate
list means no minimum Pango version is needed (spec open item closed).

- [ ] **Step 1: Write the failing tests**

Append to `SKT/core/test_fonts.py`:

```python
def test_is_known_family():
    system = ["DejaVu Sans", "Noto Serif"]
    assert fonts.is_known_family("dejavu sans", system)
    assert fonts.is_known_family("sans-serif", system)
    assert not fonts.is_known_family("Totally Missing", system)
    family = fonts.install_font(FONT_FILE)[0]
    assert fonts.is_known_family(family, system)
```

Append to `SKT/ui_gtk/test_font_properties.py`, and add
`from pathlib import Path` and `from sketcher.core import fonts` to the
imports:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py::test_is_known_family`
Expected: FAIL, `fonts` has no attribute `is_known_family`.

- [ ] **Step 3: Add `is_known_family`**

In `SK/core/fonts.py` add `from collections.abc import Iterable` to the
imports, and after `FONT_SUFFIXES` add:

```python
GENERIC_FAMILIES = ("sans-serif", "serif", "monospace")
```

At the end of the file add:

```python
def is_known_family(family: str, system_families: Iterable[str]) -> bool:
    """True when *family* is a generic family, an installed custom
    font or one of *system_families* (compared case-insensitively).
    raygeo silently substitutes unknown families, so the UI uses this
    to warn before the wrong face is engraved."""
    name = family.lower()
    if name in GENERIC_FAMILIES or is_custom_family(family):
        return True
    return name in {system.lower() for system in system_families}
```

- [ ] **Step 4: Add the rows to the widget**

In `SK/ui_gtk/font_properties.py` extend the imports:

```python
from pathlib import Path
```

```python
from gi.repository import Adw, Gio, GLib, Gtk, Pango
```

```python
from ..core import fonts
```

In `_build_ui`, directly after `self.add(self.font_family_row)` add:

```python
        self.missing_font_row = Adw.ActionRow()
        self.missing_font_row.set_title(_("Font Not Installed"))
        self.missing_font_row.set_subtitle(
            _("A substitute font is used. Install the font or pick another.")
        )
        self.missing_font_row.add_prefix(get_icon("warning-symbolic"))
        self.missing_font_row.set_visible(False)
        self.add(self.missing_font_row)

        self.custom_font_row = Adw.ComboRow()
        self.custom_font_row.set_title(_("Custom Font"))
        self.custom_font_row.connect(
            "notify::selected", self._on_custom_font_selected
        )
        self.add(self.custom_font_row)

        self.install_font_row = Adw.ActionRow()
        self.install_font_row.set_title(_("Install Font…"))
        self.install_font_row.set_activatable(True)
        self.install_font_row.connect(
            "activated", self._on_install_font_activated
        )
        self.add(self.install_font_row)

        self.remove_font_row = Adw.ActionRow()
        self.remove_font_row.set_title(_("Remove Custom Font"))
        self.remove_font_row.set_activatable(True)
        self.remove_font_row.connect(
            "activated", self._on_remove_font_activated
        )
        self.add(self.remove_font_row)
```

In `_update_ui_from_model`, inside the `try:` block after
`self.font_family_row.set_subtitle(self._current_font_family)` add:

```python
            self._refresh_custom_fonts()
```

After `_update_ui_from_model` add:

```python
    def _system_families(self) -> list[str]:
        """Family names known to the system font map."""
        return [
            family.get_name()
            for family in self.get_pango_context().list_families()
        ]

    def _refresh_custom_fonts(self):
        """Rebuilds the custom font list and the missing-font warning
        for the current family. Callers hold ``_in_update``."""
        families = fonts.list_custom_families()
        self.custom_font_row.set_model(
            Gtk.StringList.new([_("None")] + families)
        )
        selected = 0
        if self._current_font_family in families:
            selected = families.index(self._current_font_family) + 1
        self.custom_font_row.set_selected(selected)
        self.remove_font_row.set_sensitive(selected > 0)
        self.missing_font_row.set_visible(
            not fonts.is_known_family(
                self._current_font_family, self._system_families()
            )
        )

    def _set_font_family(self, family: str):
        """Selects *family* and applies it to the text entity."""
        self._in_update = True
        try:
            self._current_font_family = family
            self.font_family_row.set_subtitle(family)
            self._refresh_custom_fonts()
        finally:
            self._in_update = False
        self._apply_font_config()

    def _on_custom_font_selected(self, row, *args):
        """Handles a choice in the custom font list."""
        if self._in_update or self._text_entity_id is None:
            return
        index = row.get_selected()
        families = fonts.list_custom_families()
        if 0 < index <= len(families):
            self._set_font_family(families[index - 1])

    def _install_font_file(self, path: Path):
        """Installs a font file and selects its first family."""
        try:
            families = fonts.install_font(path)
        except ValueError as e:
            logger.warning(f"Font install failed: {e}")
            self.install_font_row.set_subtitle(
                _("Could not install {name}").format(name=path.name)
            )
            return
        self.install_font_row.set_subtitle("")
        self._set_font_family(families[0])

    def _on_install_font_activated(self, row, *args):
        """Opens a file dialog to pick a font file to install."""
        font_filter = Gtk.FileFilter()
        font_filter.set_name(_("Font Files"))
        font_filter.add_pattern("*.ttf")
        font_filter.add_pattern("*.otf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(font_filter)
        dialog = Gtk.FileDialog.new()
        dialog.set_title(_("Install Font"))
        dialog.set_filters(filters)
        dialog.set_default_filter(font_filter)
        dialog.open(self.editor.parent_window, None, self._on_font_file_chosen)

    def _on_font_file_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return
        if file and file.get_path():
            self._install_font_file(Path(file.get_path()))

    def _on_remove_font_activated(self, row, *args):
        """Removes the selected custom font and falls back to
        sans-serif."""
        if self._in_update or self._text_entity_id is None:
            return
        if not fonts.is_custom_family(self._current_font_family):
            return
        fonts.remove_font(self._current_font_family)
        self._set_font_family("sans-serif")
```

In `_update_ui_from_font_description` (system font chooser result), inside
the `if family:` block after the `set_subtitle` line add:

```python
                self._refresh_custom_fonts()
```

- [ ] **Step 5: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py`
Expected: PASS.
Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/fonts.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_fonts.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py
git commit -m "feat(sketcher): custom font list and missing-font warning"
```

---

### Task 16: Text preset storage (Phase 6)

Executor tier: SONNET
Depends on: Task 2
Parallel-safe with: Task 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21

**Files:**

- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/text_presets.py`
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_presets.py`

**Interfaces:**

- Consumes: `STYLE_DEFAULTS` (Task 2); `FontConfig.to_dict()` /
`FontConfig.from_dict(data)`; `get_addon_data_dir`.
- Produces (in `sketcher.core.text_presets`):
  - `PRESET_STYLE_KEYS: tuple[str, ...]` (every `STYLE_DEFAULTS` key except
  `path_entity_id` and `content_bottom`: no content, no path binding)
  - `@dataclass TextPreset(name: str, font: dict, style: dict)` with
  `font_config() -> FontConfig`
  - `preset_from_entity(name: str, entity: TextBoxEntity) -> TextPreset`
  - `load_presets() -> list[TextPreset]` (sorted by name; `[]` for a
  missing or corrupt file)
  - `save_preset(preset: TextPreset) -> None` (replaces a preset of the
  same name; atomic write)
  - `delete_preset(name: str) -> None`
  - file: `get_addon_data_dir("sketcher") / "text_presets.json"`

- [ ] **Step 1: Write the failing tests**

Create `SKT/core/test_text_presets.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_presets.py`
Expected: collection error, `cannot import name 'text_presets'`.

- [ ] **Step 3: Implement `SK/core/text_presets.py`**

```python
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


def load_presets() -> list[TextPreset]:
    """All saved presets, sorted by name. A missing or unreadable file
    yields an empty list."""
    try:
        data = json.loads(presets_path().read_text(encoding="utf-8"))
        items = data["presets"]
    except FileNotFoundError:
        return []
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"Cannot read text presets: {e}")
        return []
    if not isinstance(items, list):
        return []
    presets = [p for p in map(_parse, items) if p is not None]
    return sorted(presets, key=lambda preset: preset.name.lower())


def _write(presets: list[TextPreset]) -> None:
    path = presets_path()
    tmp = path.with_suffix(".json.tmp")
    payload = {
        "presets": [
            {"name": p.name, "font": p.font, "style": p.style}
            for p in presets
        ]
    }
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def save_preset(preset: TextPreset) -> None:
    """Saves *preset*, replacing any preset of the same name."""
    others = [p for p in load_presets() if p.name != preset.name]
    _write(others + [preset])


def delete_preset(name: str) -> None:
    """Deletes the preset called *name*, if there is one."""
    presets = load_presets()
    remaining = [p for p in presets if p.name != name]
    if len(remaining) != len(presets):
        _write(remaining)
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_presets.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/text_presets.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_text_presets.py
git commit -m "feat(sketcher): store text presets"
```

---

### Task 17: Preset rows in Font Properties (Phase 6)

Executor tier: SONNET
Depends on: Task 5, Task 16. Runs after Task 15 if Phase 5 has landed, otherwise after the latest finished task among 5, 7, 11 (all edit `font_properties.py`).
Parallel-safe with: Task 8, 9, 12, 13, 14, 18, 19, 20, 21

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py`
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`

**Interfaces:**

- Consumes: `load_presets`, `save_preset`, `delete_preset`,
`preset_from_entity`, `TextPreset.font_config()`, `TextPreset.style`
(Task 16); `ModifyTextPropertyCommand(..., new_style=...)` (Task 3);
Task 5 fixture.
- Produces: widget attributes `preset_row` (`Adw.ComboRow`),
`save_preset_row` (`Adw.EntryRow`), `delete_preset_row`; methods
`_apply_preset(preset)`, `_on_save_preset_applied(row)`,
`_on_delete_preset_activated(row)`.
- Applying a preset goes through `ModifyTextPropertyCommand`, so it is one
undo step.

- [ ] **Step 1: Write the failing tests**

Append to `SKT/ui_gtk/test_font_properties.py`, and add
`from sketcher.core import text_presets` to the imports:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py -k preset`
Expected: FAIL, no attribute `save_preset_row`.

- [ ] **Step 3: Add the preset rows**

In `SK/ui_gtk/font_properties.py` add to the imports:

```python
from ..core import text_presets
```

In `__init__`, after `self._current_font_family = "sans-serif"` add:

```python
        self._presets: list[text_presets.TextPreset] = []
```

At the very start of `_build_ui` (before `self.font_family_row = ...`) add:

```python
        self.preset_row = Adw.ComboRow()
        self.preset_row.set_title(_("Preset"))
        self.preset_row.connect("notify::selected", self._on_preset_selected)
        self.add(self.preset_row)

        self.save_preset_row = Adw.EntryRow()
        self.save_preset_row.set_title(_("Save as Preset"))
        self.save_preset_row.set_show_apply_button(True)
        self.save_preset_row.connect("apply", self._on_save_preset_applied)
        self.add(self.save_preset_row)

        self.delete_preset_row = Adw.ActionRow()
        self.delete_preset_row.set_title(_("Delete Preset"))
        self.delete_preset_row.set_activatable(True)
        self.delete_preset_row.connect(
            "activated", self._on_delete_preset_activated
        )
        self.add(self.delete_preset_row)
```

In `set_text_entity`, directly after `self._update_style_ui(entity)` add:

```python
        self._refresh_presets()
```

After `_on_upside_down_changed` add:

```python
    def _text_entity(self) -> TextBoxEntity | None:
        """The text entity currently shown, if it still exists."""
        sketch_element = self.editor.sketch_element
        if self._text_entity_id is None or not sketch_element:
            return None
        entity = sketch_element.sketch.registry.get_entity(
            self._text_entity_id
        )
        return entity if isinstance(entity, TextBoxEntity) else None

    def _refresh_presets(self):
        """Reloads the preset list; nothing is selected afterwards."""
        self._in_update = True
        try:
            self._presets = text_presets.load_presets()
            self.preset_row.set_model(
                Gtk.StringList.new(
                    [_("Choose…")] + [p.name for p in self._presets]
                )
            )
            self.preset_row.set_selected(0)
        finally:
            self._in_update = False

    def _selected_preset(self) -> text_presets.TextPreset | None:
        index = self.preset_row.get_selected()
        if 0 < index <= len(self._presets):
            return self._presets[index - 1]
        return None

    def _apply_preset(self, preset: text_presets.TextPreset):
        """Applies font and style of *preset* as one undoable step."""
        entity = self._text_entity()
        if entity is None:
            return
        cmd = ModifyTextPropertyCommand(
            sketch=self.editor.sketch_element.sketch,
            text_entity_id=entity.id,
            new_content=entity.content,
            new_font_config=preset.font_config(),
            new_style=dict(preset.style),
        )
        self.editor.history_manager.execute(cmd)
        self._update_ui_from_model(entity.font_config)
        self._update_style_ui(entity)

    def _on_preset_selected(self, row, *args):
        """Applies the preset picked in the list."""
        if self._in_update:
            return
        preset = self._selected_preset()
        if preset is not None:
            self._apply_preset(preset)

    def _on_save_preset_applied(self, row):
        """Saves the current font and style under the entered name."""
        name = row.get_text().strip()
        entity = self._text_entity()
        if not name or entity is None:
            return
        text_presets.save_preset(text_presets.preset_from_entity(name, entity))
        row.set_text("")
        self._refresh_presets()

    def _on_delete_preset_activated(self, row, *args):
        """Deletes the preset selected in the list."""
        preset = self._selected_preset()
        if preset is None:
            return
        text_presets.delete_preset(preset.name)
        self._refresh_presets()
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py
git commit -m "feat(sketcher): text presets in font properties"
```

---

### Task 18: `job_dispatched` hook in core (Phase 7)

Executor tier: SONNET
Depends on: none
Parallel-safe with: Task 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20

**Files:**

- Modify: `rayforge/core/hooks.py` (`PLUGIN_API_VERSION` `:7`, changelog `:13`, new hookspec after `main_window_ready` `:439`)
- Modify: `rayforge/machine/cmd.py` (imports, `_run_send_action` `:303-327`, `send_job` `:422-457`, new `_notify_job_dispatched`)
- Modify: `rayforge/doceditor/file_cmd.py:1029-1073` (`export_gcode_to_path`)
- Test: `tests/machine/test_machine_cmd.py`
- Test: `tests/doceditor/test_file_cmd.py`

**Interfaces:**

- Consumes: `get_context().plugin_mgr.hook` (pluggy; `get_context` is
already imported in both files); `MachineCmd._scheduler`
(`editor.task_manager.schedule_on_main_thread`).
- Produces:
  - hookspec `job_dispatched(doc, kind)` in `RayforgeSpecs`; `kind` is
  `"send"` or `"export"`; `PLUGIN_API_VERSION = 22`.
  - `MachineCmd._notify_job_dispatched(kind: str) -> None`, scheduled on the
  main thread.
  - `MachineCmd._run_send_action(artifact, machine, on_progress, notify_dispatch: bool = True)`.
- Fires: after `driver.run` returned for a non-empty send that is not a
pointer dry run; after `write_text` succeeded in a G-code export. Does
not fire for framing, a dry run on a machine with pointer offset, an
empty job, a send that raised, the sanity check or the G-code preview
(none of those call these two code paths).

- [ ] **Step 1: Write the failing tests**

Append to `tests/machine/test_machine_cmd.py`, and add
`from rayforge.core.hooks import hookimpl` and
`from unittest.mock import AsyncMock` to the imports:

```python
class _DispatchRecorder:
    def __init__(self):
        self.calls = []

    @hookimpl
    def job_dispatched(self, doc, kind):
        self.calls.append((doc, kind))


class TestMachineCmdJobDispatched:
    """The job_dispatched hook fires only for real, successful sends."""

    @pytest.fixture
    def dispatch_spy(self, machine_cmd, mocker):
        return mocker.patch.object(machine_cmd, "_notify_job_dispatched")

    @pytest.fixture
    def fake_pipeline(self, machine_cmd, job_artifact, mocker):
        pipeline = machine_cmd._editor.pipeline
        handle = pipeline.artifact_store.put(job_artifact, creator_tag="test")

        async def fake_generate():
            return handle

        mocker.patch.object(
            pipeline, "generate_job_artifact_async", side_effect=fake_generate
        )
        mocker.patch.object(pipeline, "invalidate_job_output")
        return pipeline

    @pytest.mark.asyncio
    async def test_send_dispatches_once(
        self, machine_cmd, doc_editor, machine, job_artifact, dispatch_spy
    ):
        await machine_cmd._run_send_action(job_artifact, machine, None)
        await asyncio.sleep(0)
        await doc_editor.wait_until_settled()

        dispatch_spy.assert_called_once_with("send")

    @pytest.mark.asyncio
    async def test_failed_send_does_not_dispatch(
        self, machine_cmd, machine, job_artifact, dispatch_spy, mocker
    ):
        mocker.patch.object(
            machine.driver, "run", side_effect=RuntimeError("boom")
        )

        with pytest.raises(RuntimeError):
            await machine_cmd._run_send_action(job_artifact, machine, None)
        await asyncio.sleep(0)

        dispatch_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_job_does_not_dispatch(
        self, machine_cmd, machine, dispatch_spy
    ):
        empty = JobArtifact(
            ops=Ops(), distance=0.0, generation_id=1, encoded_output=None
        )

        await machine_cmd._run_send_action(empty, machine, None)
        await asyncio.sleep(0)

        dispatch_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_frame_does_not_dispatch(
        self, machine_cmd, doc_editor, machine, job_artifact, dispatch_spy,
        mocker,
    ):
        mocker.patch.object(machine.driver, "frame", new=AsyncMock())

        await machine_cmd._run_frame_action(job_artifact, machine, None)
        await asyncio.sleep(0)
        await doc_editor.wait_until_settled()

        dispatch_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_pointer_dry_run_does_not_dispatch(
        self, machine_cmd, doc_editor, machine, fake_pipeline, dispatch_spy
    ):
        head = machine.get_default_laser_head()
        head.set_pointer_offset(10.0, 20.0)
        head.set_pointer_offset_enabled(True)

        await machine_cmd.send_job(machine, pointer_dry_run=True)
        await asyncio.sleep(0)
        await doc_editor.wait_until_settled()

        dispatch_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_without_pointer_offset_dispatches(
        self, machine_cmd, doc_editor, machine, fake_pipeline, dispatch_spy
    ):
        await machine_cmd.send_job(machine, pointer_dry_run=True)
        await asyncio.sleep(0)
        await doc_editor.wait_until_settled()

        dispatch_spy.assert_called_once_with("send")

    @pytest.mark.asyncio
    async def test_regular_send_job_dispatches(
        self, machine_cmd, doc_editor, machine, fake_pipeline, dispatch_spy
    ):
        await machine_cmd.send_job(machine)
        await asyncio.sleep(0)
        await doc_editor.wait_until_settled()

        dispatch_spy.assert_called_once_with("send")

    def test_notify_calls_the_plugin_hook(
        self, machine_cmd, doc_editor, context_initializer
    ):
        recorder = _DispatchRecorder()
        context_initializer.plugin_mgr.register(recorder)
        try:
            machine_cmd._notify_job_dispatched("send")
        finally:
            context_initializer.plugin_mgr.unregister(recorder)

        assert recorder.calls == [(doc_editor.doc, "send")]
```

Append to the `TestExportGcodeToPath` class in
`tests/doceditor/test_file_cmd.py`, and add
`from rayforge.core.hooks import hookimpl`,
`from rayforge.context import get_context` and
`from rayforge.pipeline.artifact import JobArtifact` to the imports:

```python
    def _export(self, file_cmd, export_path, machine_code):
        artifact = MagicMock(spec=JobArtifact)
        artifact.machine_code = machine_code
        store = file_cmd._editor.pipeline.artifact_store
        with (
            patch.object(
                file_cmd._editor.pipeline, "generate_job_artifact"
            ) as mock_generate,
            patch.object(store, "checkout_handle") as mock_checkout,
        ):
            mock_checkout.return_value.__enter__.return_value = artifact
            mock_generate.side_effect = lambda when_done: when_done(
                MagicMock(), None
            )
            file_cmd.export_gcode_to_path(export_path)

    def test_export_gcode_dispatches_job(self, file_cmd, tmp_path):
        """A successful export fires job_dispatched once."""
        calls = []

        class Recorder:
            @hookimpl
            def job_dispatched(self, doc, kind):
                calls.append((doc, kind))

        recorder = Recorder()
        plugin_mgr = get_context().plugin_mgr
        plugin_mgr.register(recorder)
        try:
            self._export(file_cmd, tmp_path / "out.gcode", "G0 X0\n")
        finally:
            plugin_mgr.unregister(recorder)

        assert (tmp_path / "out.gcode").read_text() == "G0 X0\n"
        assert calls == [(file_cmd._editor.doc, "export")]

    def test_failed_export_does_not_dispatch_job(self, file_cmd, tmp_path):
        """An export without G-code data fires nothing."""
        calls = []

        class Recorder:
            @hookimpl
            def job_dispatched(self, doc, kind):
                calls.append(kind)

        recorder = Recorder()
        plugin_mgr = get_context().plugin_mgr
        plugin_mgr.register(recorder)
        try:
            self._export(file_cmd, tmp_path / "out.gcode", None)
        finally:
            plugin_mgr.unregister(recorder)

        assert calls == []
        assert not (tmp_path / "out.gcode").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test tests/machine/test_machine_cmd.py::TestMachineCmdJobDispatched tests/doceditor/test_file_cmd.py::TestExportGcodeToPath`
Expected: FAIL (`MachineCmd` has no attribute `_notify_job_dispatched`;
pluggy rejects `job_dispatched` as an unknown hook or records no call).

- [ ] **Step 3: Add the hookspec**

In `rayforge/core/hooks.py` change line 7 to:

```python
PLUGIN_API_VERSION = 22
```

In the changelog string, directly above the `Version 21` heading, add:

```
Version 22
----------
Added the ``job_dispatched(doc, kind)`` hook. It is called on the main
thread after a job was handed off successfully: ``kind`` is ``"send"``
when the machine driver accepted and ran a job, and ``"export"`` when
G-code was written to a file. Framing, pointer dry runs, failed or
empty jobs, sanity checks and previews do not call it.

```

At the end of `RayforgeSpecs`, after the `main_window_ready` hookspec, add:

```python

    @hookspec
    def job_dispatched(self, doc, kind):
        """
        Called after a job was handed off successfully.

        Fires once per job on the main thread: after the machine driver
        ran a sent job, or after exported G-code was written to disk.
        Framing, pointer dry runs, failed or empty jobs, sanity checks
        and previews do not fire it. Implementations must not raise.

        .. versionadded:: 22

        Args:
            doc: The Doc the job was generated from.
            kind: ``"send"`` for a job sent to the machine, ``"export"``
              for a G-code export.
        """
```

- [ ] **Step 4: Call the hook after a send**

In `rayforge/machine/cmd.py` add to the imports at the top:

```python
from functools import partial
```

Add a method to `MachineCmd` directly after `_progress_handler`:

```python
    def _notify_job_dispatched(self, kind: str) -> None:
        """Tells addons that a job was handed off successfully."""
        get_context().plugin_mgr.hook.job_dispatched(
            doc=self._editor.doc, kind=kind
        )
```

Change `_run_send_action`: add the keyword parameter and the call. The
signature becomes:

```python
    async def _run_send_action(
        self,
        artifact: JobArtifact,
        machine: Machine,
        on_progress: Callable[[dict], None] | None,
        notify_dispatch: bool = True,
    ):
```

and after the existing `await self._execute_monitored_job(...)` call at the
end of the method add:

```python
        if notify_dispatch and not artifact.ops.is_empty():
            self._scheduler(self._notify_job_dispatched, "send")
```

In `send_job`, replace

```python
                final_job_action=self._run_send_action,
```

with:

```python
                final_job_action=partial(
                    self._run_send_action,
                    notify_dispatch=not (
                        pointer_dry_run and machine.has_pointer_offset()
                    ),
                ),
```

- [ ] **Step 5: Call the hook after an export**

In `rayforge/doceditor/file_cmd.py`, in `export_gcode_to_path`, directly
after

```python
                    self._editor.notification_requested.send(self, message=msg)
```

(the success notification inside the `with` block) add:

```python
                    get_context().plugin_mgr.hook.job_dispatched(
                        doc=self._editor.doc, kind="export"
                    )
```

- [ ] **Step 6: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test tests/machine/test_machine_cmd.py tests/doceditor/test_file_cmd.py::TestExportGcodeToPath`
Expected: PASS (new and existing tests, including
`TestMachineCmdPointerDryRun`).

If `test_empty_job_does_not_dispatch` fails while constructing
`JobArtifact` (required arguments differ), build the empty artifact the
way the `job_artifact` fixture in the same file does, with `Ops()` in
place of `simple_ops`.

- [ ] **Step 7: Commit**

```bash
git add rayforge/core/hooks.py rayforge/machine/cmd.py rayforge/doceditor/file_cmd.py tests/machine/test_machine_cmd.py tests/doceditor/test_file_cmd.py
git commit -m "feat(core): add job_dispatched addon hook (API 22)"
```

---

### Task 19: Serial counter storage (Phase 7)

Executor tier: SONNET
Depends on: none
Parallel-safe with: Task 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18

**Files:**

- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/serial.py`
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial.py`

**Interfaces:**

- Consumes: `get_addon_data_dir`.
- Produces (in `sketcher.core.serial`; this module must not import
`sketcher.core.sketch` or `sketcher.core.entities`):
  - `DEFAULT_NAME = "default"`
  - `@dataclass SerialCounter(name: str, value: int = 1, start: int = 1, step: int = 1, padding: int = 0, prefix: str = "", suffix: str = "")`
  with `format() -> str` and `reset() -> None` (`value = start`)
  - `serials_path() -> Path` (`get_addon_data_dir("sketcher") / "serials.json"`)
  - `load_counters() -> dict[str, SerialCounter]` (`{}` for a missing file;
  raises `ValueError` for a corrupt one)
  - `save_counters(counters: dict[str, SerialCounter]) -> None` (atomic)
  - `peek(name: str = DEFAULT_NAME) -> str` (current formatted value;
  never writes, never advances; unknown names format a default counter)
  - `advance(names: Iterable[str]) -> None` (re-reads the file, adds each
  counter's `step` once, creates missing counters, writes)
  - `find_serial_names(text: str) -> set[str]` (counter names used by
  `serial()` / `serial("name")` calls with a literal or no argument)

- [ ] **Step 1: Write the failing tests**

Create `SKT/core/test_serial.py`:

```python
import json

import pytest
from sketcher.core import serial
from sketcher.core.serial import (
    DEFAULT_NAME,
    SerialCounter,
    advance,
    find_serial_names,
    load_counters,
    peek,
    save_counters,
)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    return tmp_path


def test_format_with_padding_prefix_and_suffix():
    counter = SerialCounter(
        "batch", value=7, padding=4, prefix="SN-", suffix="/A"
    )
    assert counter.format() == "SN-0007/A"


def test_format_without_padding():
    assert SerialCounter("x", value=12).format() == "12"


def test_reset_returns_to_start():
    counter = SerialCounter("x", value=40, start=5)
    counter.reset()
    assert counter.value == 5


def test_peek_unknown_counter_uses_defaults_and_writes_nothing():
    assert peek("new") == "1"
    assert peek() == "1"
    assert not serial.serials_path().exists()


def test_peek_never_advances():
    save_counters({"a": SerialCounter("a", value=3)})
    assert [peek("a"), peek("a"), peek("a")] == ["3", "3", "3"]


def test_advance_adds_step_and_persists():
    save_counters({"a": SerialCounter("a", value=10, step=5)})
    advance(["a"])
    assert peek("a") == "15"
    assert load_counters()["a"].value == 15


def test_advance_counts_each_name_once():
    save_counters({"a": SerialCounter("a", value=1)})
    advance(["a", "a", "a"])
    assert load_counters()["a"].value == 2


def test_advance_creates_missing_counter():
    advance([DEFAULT_NAME])
    assert load_counters()[DEFAULT_NAME].value == 2


def test_advance_leaves_other_counters_alone():
    save_counters(
        {"a": SerialCounter("a", value=1), "b": SerialCounter("b", value=9)}
    )
    advance(["a"])
    assert load_counters()["b"].value == 9


def test_advance_with_no_names_writes_nothing():
    advance([])
    assert not serial.serials_path().exists()


def test_two_readers_share_the_file():
    """A second window that advanced in between is not overwritten."""
    save_counters({"a": SerialCounter("a", value=1)})
    advance(["a"])
    other_window = load_counters()
    other_window["a"].value += other_window["a"].step
    save_counters(other_window)

    advance(["a"])

    assert load_counters()["a"].value == 4


def test_counter_fields_round_trip():
    original = SerialCounter(
        "a", value=3, start=2, step=4, padding=5, prefix="P", suffix="S"
    )
    save_counters({"a": original})
    assert load_counters()["a"] == original


def test_unknown_keys_and_bad_entries_are_ignored():
    serial.serials_path().write_text(
        json.dumps(
            {
                "counters": [
                    {"name": "ok", "value": 4, "future": True},
                    {"name": "bad", "value": "seven"},
                    {"value": 3},
                    "garbage",
                ]
            }
        ),
        encoding="utf-8",
    )
    counters = load_counters()
    assert list(counters) == ["ok"]
    assert counters["ok"].value == 4


def test_peek_survives_corrupt_file():
    serial.serials_path().write_text("{ nope", encoding="utf-8")
    assert peek("a") == "1"


def test_advance_backs_up_corrupt_file(data_dir):
    serial.serials_path().write_text("{ nope", encoding="utf-8")

    advance(["a"])

    backup = data_dir / "sketcher" / "serials.json.bak"
    assert backup.read_text(encoding="utf-8") == "{ nope"
    assert load_counters()["a"].value == 2


def test_save_leaves_no_temp_file(data_dir):
    save_counters({"a": SerialCounter("a")})
    assert [p.name for p in (data_dir / "sketcher").iterdir()] == [
        "serials.json"
    ]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("plain", set()),
        ("{serial()}", {DEFAULT_NAME}),
        ('{serial("batch")}', {"batch"}),
        ("{serial('a')} and {serial( \"b\" ):>8}", {"a", "b"}),
        ("SN {serial()} / {serial('x')}", {DEFAULT_NAME, "x"}),
        ("{serial_number}", set()),
        ("{myserial()}", set()),
    ],
)
def test_find_serial_names(text, expected):
    assert find_serial_names(text) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial.py`
Expected: collection error, `cannot import name 'serial'`.

- [ ] **Step 3: Implement `SK/core/serial.py`**

```python
"""Persistent, named serial-number counters for text templates.

``{serial("name")}`` in a text box shows the counter's current value
and never advances it. Counters advance once per dispatched job (see
``serial_dispatch``), so the canvas always shows exactly what the next
job will engrave.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from rayforge.config import get_addon_data_dir

logger = logging.getLogger(__name__)

DEFAULT_NAME = "default"

_SERIAL_CALL = re.compile(
    r"""(?<![\w.])serial\(\s*(?:(["'])(.*?)\1)?\s*\)"""
)
_INT_FIELDS = ("value", "start", "step", "padding")
_STR_FIELDS = ("name", "prefix", "suffix")


@dataclass
class SerialCounter:
    name: str
    value: int = 1
    start: int = 1
    step: int = 1
    padding: int = 0
    prefix: str = ""
    suffix: str = ""

    def format(self) -> str:
        """Prefix, zero-padded value and suffix."""
        number = f"{self.value:0{max(self.padding, 0)}d}"
        return f"{self.prefix}{number}{self.suffix}"

    def reset(self) -> None:
        self.value = self.start


def serials_path() -> Path:
    return get_addon_data_dir("sketcher") / "serials.json"


def _parse(item: Any) -> SerialCounter | None:
    if not isinstance(item, dict) or not item.get("name"):
        return None
    known = {f.name for f in fields(SerialCounter)}
    data = {key: value for key, value in item.items() if key in known}
    for key in _INT_FIELDS:
        value = data.get(key, 0)
        if not isinstance(value, int) or isinstance(value, bool):
            return None
    for key in _STR_FIELDS:
        if not isinstance(data.get(key, ""), str):
            return None
    return SerialCounter(**data)


def load_counters() -> dict[str, SerialCounter]:
    """
    Reads all counters from disk, keyed by name.

    A missing file yields an empty dict. Raises ValueError when the
    file exists but cannot be parsed, so callers can avoid overwriting
    it blindly.
    """
    path = serials_path()
    if not path.exists():
        return {}
    try:
        items = json.loads(path.read_text(encoding="utf-8"))["counters"]
        if not isinstance(items, list):
            raise TypeError("'counters' is not a list")
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f"Cannot read {path.name}: {e}") from e
    counters = [c for c in map(_parse, items) if c is not None]
    return {counter.name: counter for counter in counters}


def save_counters(counters: dict[str, SerialCounter]) -> None:
    """Writes all counters atomically."""
    path = serials_path()
    tmp = path.with_suffix(".json.tmp")
    payload = {"counters": [asdict(c) for c in counters.values()]}
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def peek(name: str = DEFAULT_NAME) -> str:
    """The current formatted value of counter *name*. Never advances
    and never writes; an unknown counter formats its defaults."""
    try:
        counters = load_counters()
    except ValueError as e:
        logger.warning(str(e))
        counters = {}
    return counters.get(str(name), SerialCounter(str(name))).format()


def advance(names: Iterable[str]) -> None:
    """
    Advances each named counter by its step, once per name.

    The file is re-read first so a second Rayforge window that advanced
    in the meantime is not overwritten. A corrupt file is kept as
    ``serials.json.bak`` and counting restarts from defaults.
    """
    wanted = set(names)
    if not wanted:
        return
    # shortcut: read-modify-write without a file lock, upgrade if two
    # windows dispatching in the same instant becomes a real case
    try:
        counters = load_counters()
    except ValueError as e:
        logger.error(f"{e}; keeping it as serials.json.bak")
        path = serials_path()
        os.replace(path, path.with_suffix(".json.bak"))
        counters = {}
    for name in sorted(wanted):
        counter = counters.setdefault(name, SerialCounter(name))
        counter.value += counter.step
    save_counters(counters)


def find_serial_names(text: str) -> set[str]:
    """Counter names used by ``serial()`` calls in a text template.
    Only literal or missing arguments are recognised."""
    return {
        match.group(2) or DEFAULT_NAME
        for match in _SERIAL_CALL.finditer(text)
    }
```

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/serial.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial.py
git commit -m "feat(sketcher): persistent serial counters"
```

---

### Task 20: `serial()` template function (Phase 7)

Executor tier: SONNET
Depends on: Task 19
Parallel-safe with: Task 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/template_functions.py` (docstring table `:12-24`, `TemplateFunction` `:34-37`, built-ins `:50-57`, `register_template_function` docstring `:60-75`, `unregister_template_function` `:78-94`)
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_text_templates.py`

**Interfaces:**

- Consumes: `sketcher.core.serial.peek(name="default") -> str`,
`advance(names)`, `save_counters`, `SerialCounter` (Task 19).
- Produces: built-in template function `serial` (`{serial()}`,
`{serial("name")}`); `TemplateFunction = Callable[..., object]`;
`serial` cannot be unregistered.

Template expressions are evaluated by `ExpressionMap`
(`rayforge/core/expression/expression_map.py:12`), which calls the function
itself, so arguments already work; only the type alias and docs say
"zero-argument" today.

- [ ] **Step 1: Write the failing tests**

Append to `SKT/core/test_sketch_text_templates.py`, and add `import pytest`,
`from sketcher.core.serial import SerialCounter, advance, save_counters`
and
`from sketcher.core.template_functions import get_template_functions, unregister_template_function`
to the imports (merge with existing import lines from the same modules):

```python
@pytest.fixture
def serial_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("rayforge.config.ADDON_DATA_DIR", tmp_path)
    return tmp_path


def test_serial_resolves_current_value(serial_dir):
    save_counters(
        {"batch": SerialCounter("batch", value=7, padding=3, prefix="SN")}
    )
    s = Sketch()
    box = _add_text_box(s, '{serial("batch")}')
    s.solve()
    assert s._resolve_text_content(box) == "SN007"


def test_serial_default_counter(serial_dir):
    s = Sketch()
    box = _add_text_box(s, "No. {serial()}")
    s.solve()
    assert s._resolve_text_content(box) == "No. 1"


def test_resolving_serial_does_not_advance(serial_dir):
    s = Sketch()
    box = _add_text_box(s, "{serial()}")
    for _ in range(3):
        s.solve()
        assert s._resolve_text_content(box) == "1"
    assert not (serial_dir / "sketcher" / "serials.json").exists()


def test_serial_changes_after_advance_and_re_solve(serial_dir):
    s = Sketch()
    box = _add_text_box(s, "{serial()}")
    s.solve()
    assert s._resolve_text_content(box) == "1"

    advance(["default"])
    assert s._resolve_text_content(box) == "1"

    s.solve()
    assert s._resolve_text_content(box) == "2"


def test_serial_is_a_protected_builtin(serial_dir):
    unregister_template_function("serial")
    assert "serial" in get_template_functions()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_text_templates.py -k serial`
Expected: FAIL (`{serial()}` does not resolve; `serial` is not registered).

- [ ] **Step 3: Register the built-in**

In `SK/core/template_functions.py`:

Add a row to the docstring table, after the `uuid4()` row and before the
closing `=====` line:

```
``serial(name)``    Current value of a persistent serial counter
                    (``str``); ``name`` defaults to ``"default"``.
                    Advances once per sent or exported job.
```

Add the import below `from datetime import datetime, timezone`:

```python
from .serial import peek as _serial_peek
```

Replace the alias and its comment:

```python
# A call returning the value to substitute.  Callables are invoked
# fresh per evaluation so that volatile values (e.g. uuids) differ
# between renders.  The template expression calls them itself, so
# they may take arguments (``{serial("batch")}``).
TemplateFunction = Callable[..., object]
```

After the `uuid4` registration line add:

```python
_register_builtin("serial", _serial_peek)
```

In the docstring of `register_template_function`, replace

```
        func: A zero-argument callable returning the substitution value.
```

with:

```
        func: A callable returning the substitution value; template
            expressions may pass it arguments.
```

In `unregister_template_function`, add `"serial",` to the tuple of
protected names, after `"uuid4",`.

- [ ] **Step 4: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_text_templates.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_array_text_template.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/template_functions.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_sketch_text_templates.py
git commit -m "feat(sketcher): serial() template function"
```

---

### Task 21: Advance serials on dispatch and refresh on load (Phase 7)

Executor tier: SONNET
Depends on: Task 2, Task 18, Task 20
Parallel-safe with: Task 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17

**Files:**

- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/serial_dispatch.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/frontend.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/rayforge-addon.yaml:4`
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial_dispatch.py`

`frontend.py` is also edited by Task 14. If Task 14 has not landed yet,
there is no conflict; if it has, keep its `rayforge_init` hook and import.

**Interfaces:**

- Consumes: hook `job_dispatched(doc, kind)` (Task 18);
`find_serial_names`, `advance` (Task 19); `TextBoxEntity.content_bottom`
(Task 2); `Doc.all_workpieces` (`rayforge/core/doc.py:312`);
`WorkPiece.get_geometry_provider()` (`rayforge/core/workpiece.py:618`);
`WorkPiece.regenerate_from_geometry_provider()` (`:1518`, resets
`_resolved_text_cache`); `DocEditor.document_changed`
(`rayforge/doceditor/editor.py:120`, sent as `document_changed.send(editor)`);
`main_window.doc_editor` (`rayforge/ui_gtk/mainwindow.py:177`).
- Produces (in `sketcher.core.serial_dispatch`):
  - `serial_names_in_sketch(sketch: Sketch) -> set[str]`
  - `serial_workpieces(doc) -> list[tuple[WorkPiece, set[str]]]`
  - `refresh_serials(doc) -> None` (regenerates every workpiece whose
  sketch uses `serial(`)
  - `on_job_dispatched(doc) -> None` (advance each used counter once, then
  refresh; never raises)
- Sketcher manifest `api_version: 22`.

- [ ] **Step 1: Write the failing tests**

Create `SKT/core/test_serial_dispatch.py`:

```python
import pytest
from raygeo.geo.shape.text import FontConfig
from sketcher.core import Sketch
from sketcher.core.serial import load_counters
from sketcher.core.serial_dispatch import (
    on_job_dispatched,
    refresh_serials,
    serial_names_in_sketch,
    serial_workpieces,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial_dispatch.py`
Expected: collection error, `No module named 'sketcher.core.serial_dispatch'`.

- [ ] **Step 3: Implement `SK/core/serial_dispatch.py`**

```python
"""Connects serial counters to documents: which workpieces use them,
advancing them when a job is dispatched, and refreshing their text.

Resolved text is cached per workpiece and saved with the project, so
a number that was already engraved would be shown and engraved again
unless the cache is dropped after an advance and after loading.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .entities import TextBoxEntity
from .serial import advance, find_serial_names
from .sketch import Sketch

if TYPE_CHECKING:
    from rayforge.core.doc import Doc
    from rayforge.core.workpiece import WorkPiece

logger = logging.getLogger(__name__)


def serial_names_in_sketch(sketch: Sketch) -> set[str]:
    """Names of all serial counters used by the sketch's text boxes."""
    names: set[str] = set()
    for entity in sketch.registry.entities:
        if isinstance(entity, TextBoxEntity):
            names |= find_serial_names(entity.content)
            names |= find_serial_names(entity.content_bottom)
    return names


def serial_workpieces(doc: Doc) -> list[tuple[WorkPiece, set[str]]]:
    """Workpieces whose sketch uses a serial counter, with the names."""
    result = []
    for workpiece in doc.all_workpieces:
        provider = workpiece.get_geometry_provider()
        if not isinstance(provider, Sketch):
            continue
        names = serial_names_in_sketch(provider)
        if names:
            result.append((workpiece, names))
    return result


def _regenerate(workpieces: list[WorkPiece]) -> None:
    for workpiece in workpieces:
        workpiece.regenerate_from_geometry_provider()


def refresh_serials(doc: Doc) -> None:
    """Re-resolves the text of every workpiece that shows a serial."""
    _regenerate([workpiece for workpiece, _ in serial_workpieces(doc)])


def on_job_dispatched(doc: Doc) -> None:
    """Advances every counter the document uses, once each, and
    refreshes the affected workpieces. Never raises: a dispatched job
    must not fail because of a counter."""
    try:
        usage = serial_workpieces(doc)
        if not usage:
            return
        advance(set().union(*(names for _, names in usage)))
        _regenerate([workpiece for workpiece, _ in usage])
    except Exception:
        logger.exception("Failed to advance serial numbers")
```

- [ ] **Step 4: Hook it up in the frontend and bump the manifest**

In `SK/frontend.py` add below the existing `hookimpl` import:

```python
from .core.serial_dispatch import on_job_dispatched, refresh_serials
```

After `ADDON_NAME = "sketcher"` add:

```python
_doc_editor = None


def _on_document_changed(editor, **kwargs):
    """Refresh serial numbers cached in a newly loaded document."""
    refresh_serials(editor.doc)


@hookimpl
def job_dispatched(doc, kind):
    """Advance the serial counters used by the dispatched document."""
    on_job_dispatched(doc)
```

Replace the `main_window_ready` and `on_unload` hooks with:

```python
@hookimpl
def main_window_ready(main_window):
    """Set up sketch studio and mode command when main window is ready."""
    global _doc_editor
    from .ui_gtk import setup_sketch_page

    setup_sketch_page(main_window)
    _doc_editor = main_window.doc_editor
    _doc_editor.document_changed.connect(_on_document_changed)
    refresh_serials(_doc_editor.doc)


@hookimpl
def on_unload():
    """Clean up sketch studio when addon is disabled."""
    global _doc_editor
    logger.info("on_unload hook called, tearing down sketch page")
    from .ui_gtk import teardown_sketch_page

    teardown_sketch_page()
    if _doc_editor is not None:
        _doc_editor.document_changed.disconnect(_on_document_changed)
        _doc_editor = None
```

In `rayforge-addon.yaml` change line 4 from `api_version: 19` to:

```yaml
api_version: 22
```

- [ ] **Step 5: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run test rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial_dispatch.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/test_sketcher_workpiece.py`
Expected: PASS.
Run: `pixi run test tests/addon_mgr`
Expected: PASS (manifest version 22 is accepted because
`PLUGIN_API_VERSION` is 22 after Task 18).

If `_add_workpiece` in the test fails because the workpiece cannot find
its provider, copy the document setup from
`SKT/test_sketcher_workpiece.py:105-110` (`doc.add_asset(sketch)`,
`wp.geometry_provider_uid = sketch.uid`, add the workpiece to the layer).

- [ ] **Step 6: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/core/serial_dispatch.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/frontend.py rayforge/builtin_addons/rayforge-addon-sketcher/rayforge-addon.yaml rayforge/builtin_addons/rayforge-addon-sketcher/tests/core/test_serial_dispatch.py
git commit -m "feat(sketcher): advance serial numbers when a job is dispatched"
```

---

### Task 22: Serial numbers settings page and Insert Serial row (Phase 7)

Executor tier: SONNET
Depends on: Task 19, Task 21. Runs after the latest finished task among 5, 7, 11, 15, 17 (all edit `font_properties.py`).
Parallel-safe with: Task 8, 9, 12, 13, 14, 16, 18

**Files:**

- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/serial_settings.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/frontend.py`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py`
- Create: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_serial_settings.py`
- Test: `rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`

**Interfaces:**

- Consumes: `load_counters`, `save_counters`, `SerialCounter`,
`DEFAULT_NAME` (Task 19); hook
`register_settings_pages(settings_page_registry)`
(`rayforge/core/hooks.py:404`);
`settings_page_registry.register(PageClass, addon_name=...)`
(`rayforge/ui_gtk/settings/registry.py:34`);
`TrackedPreferencesPage` (`rayforge/ui_gtk/shared/preferences_page.py:6`,
pattern: `ToolManagerPage` in
`rayforge/builtin_addons/rayforge-addon-tools/tool_library/frontend.py:158`);
`SpinRow(title, subtitle=None, *, lower, upper, step_increment, digits, value)`
with `get_int_value()` and `value_changed`.
- Produces:
  - `sketcher.ui_gtk.serial_settings.SerialSettingsPage` (no-argument
  constructor; `key = "serial-numbers"`; methods `add_counter(name)`,
  `reset_counter(name)`, `delete_counter(name)`, `update_counter(name, **fields)`)
  - widget attribute `insert_serial_row` on `FontPropertiesWidget` and
  `_on_insert_serial_activated(row)`, which appends `{serial()}` to the
  text content through `ModifyTextPropertyCommand`.

- [ ] **Step 1: Write the failing tests**

Create `SKT/ui_gtk/test_serial_settings.py`:

```python
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
```

Append to `SKT/ui_gtk/test_font_properties.py`:

```python
@pytest.mark.ui
def test_insert_serial_appends_template(widget_with_box):
    widget, sketch, tb_id = widget_with_box
    entity = sketch.registry.get_entity(tb_id)

    widget._on_insert_serial_activated(widget.insert_serial_row)

    assert entity.content == "Hello{serial()}"

    widget.editor.history_manager.undo()
    assert entity.content == "Hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_serial_settings.py`
Expected: collection error, `No module named 'sketcher.ui_gtk.serial_settings'`.

- [ ] **Step 3: Implement the settings page**

Create `SK/ui_gtk/serial_settings.py`:

```python
"""Settings page for the global serial-number counters."""

import logging
from gettext import gettext as _

from gi.repository import Adw

from rayforge.ui_gtk.shared.pref_rows import SpinRow
from rayforge.ui_gtk.shared.preferences_page import TrackedPreferencesPage

from ..core.serial import SerialCounter, load_counters, save_counters

logger = logging.getLogger(__name__)

_INT_ROWS = (
    ("value", _("Current Value"), -1e9),
    ("start", _("Start"), -1e9),
    ("step", _("Step"), -1e6),
    ("padding", _("Zero Padding"), 0.0),
)
_TEXT_ROWS = (("prefix", _("Prefix")), ("suffix", _("Suffix")))


class SerialSettingsPage(TrackedPreferencesPage):
    """Lists the serial counters shared by all documents."""

    key = "serial-numbers"

    def __init__(self):
        super().__init__(
            title=_("Serial Numbers"), icon_name="view-list-symbolic"
        )
        self.counter_groups: dict[str, Adw.PreferencesGroup] = {}

        add_group = Adw.PreferencesGroup()
        add_group.set_title(_("Serial Numbers"))
        add_group.set_description(
            _(
                "Counters advance once for every job sent to the machine "
                "or exported. Use them in a text box with "
                '{serial("name")}.'
            )
        )
        self.add_row = Adw.EntryRow()
        self.add_row.set_title(_("New Counter Name"))
        self.add_row.set_show_apply_button(True)
        self.add_row.connect("apply", self._on_add_applied)
        add_group.add(self.add_row)
        self.add(add_group)

        for counter in self._load().values():
            self._add_group(counter)

    def _load(self) -> dict[str, SerialCounter]:
        try:
            return load_counters()
        except ValueError as e:
            logger.warning(str(e))
            return {}

    def _add_group(self, counter: SerialCounter) -> None:
        group = Adw.PreferencesGroup()
        group.set_title(counter.name)
        for field, title, lower in _INT_ROWS:
            row = SpinRow(
                title,
                lower=lower,
                upper=1e9,
                step_increment=1.0,
                digits=0,
                value=float(getattr(counter, field)),
            )
            row.value_changed.connect(
                self._on_int_changed, counter.name, field
            )
            group.add(row)
        for field, title in _TEXT_ROWS:
            row = Adw.EntryRow()
            row.set_title(title)
            row.set_text(getattr(counter, field))
            row.set_show_apply_button(True)
            row.connect("apply", self._on_text_applied, counter.name, field)
            group.add(row)
        group.add(
            self._button_row(_("Reset to Start"), self.reset_counter, counter)
        )
        group.add(
            self._button_row(_("Delete Counter"), self.delete_counter, counter)
        )
        self.add(group)
        self.counter_groups[counter.name] = group

    def _button_row(self, title: str, action, counter) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_activatable(True)
        row.connect("activated", lambda _row: action(counter.name))
        return row

    def _rebuild_group(self, name: str) -> None:
        group = self.counter_groups.pop(name, None)
        if group is not None:
            self.remove(group)
        counter = self._load().get(name)
        if counter is not None:
            self._add_group(counter)

    def add_counter(self, name: str) -> None:
        """Creates a counter with default settings."""
        name = name.strip()
        counters = self._load()
        if not name or name in counters:
            return
        counters[name] = SerialCounter(name)
        save_counters(counters)
        self._add_group(counters[name])

    def update_counter(self, name: str, **changes) -> None:
        """Changes fields of one counter and saves."""
        counters = self._load()
        counter = counters.get(name)
        if counter is None:
            return
        for field, value in changes.items():
            setattr(counter, field, value)
        save_counters(counters)

    def reset_counter(self, name: str) -> None:
        """Sets the counter back to its start value."""
        counters = self._load()
        if name not in counters:
            return
        counters[name].reset()
        save_counters(counters)
        self._rebuild_group(name)

    def delete_counter(self, name: str) -> None:
        counters = self._load()
        if counters.pop(name, None) is None:
            return
        save_counters(counters)
        self._rebuild_group(name)

    def _on_add_applied(self, row: Adw.EntryRow) -> None:
        self.add_counter(row.get_text())
        row.set_text("")

    def _on_int_changed(self, row, name: str, field: str) -> None:
        self.update_counter(name, **{field: row.get_int_value()})

    def _on_text_applied(self, row, name: str, field: str) -> None:
        self.update_counter(name, **{field: row.get_text()})
```

One point to verify against the code while implementing:

- `SpinRow.value_changed` is a blinker-style signal
(`rayforge/ui_gtk/shared/pref_rows/base.py`, `_StrongSignal`). If its
`connect` does not accept extra positional arguments, connect
`functools.partial(self._on_int_changed, name=counter.name, field=field)`
instead and import `partial` at the top of the file.

- [ ] **Step 4: Register the page**

In `SK/frontend.py`, add after the `job_dispatched` hook:

```python
@hookimpl
def register_settings_pages(settings_page_registry):
    """Contribute the serial-number counters page to Settings."""
    from .ui_gtk.serial_settings import SerialSettingsPage

    settings_page_registry.register(SerialSettingsPage, addon_name=ADDON_NAME)
```

(The import stays inside the function like the other GTK imports in this
file: the module is loaded before GTK is guaranteed to be initialised.)

- [ ] **Step 5: Add the Insert Serial row**

In `SK/ui_gtk/font_properties.py`, at the end of `_build_ui` add:

```python
        self.insert_serial_row = Adw.ActionRow()
        self.insert_serial_row.set_title(_("Insert Serial Number"))
        self.insert_serial_row.set_subtitle(
            _("Counters are managed in Settings")
        )
        self.insert_serial_row.set_activatable(True)
        self.insert_serial_row.connect(
            "activated", self._on_insert_serial_activated
        )
        self.add(self.insert_serial_row)
```

and add this method after `_on_upside_down_changed`:

```python
    def _on_insert_serial_activated(self, row, *args):
        """Appends the default serial-number template to the text."""
        sketch_element = self.editor.sketch_element
        if self._text_entity_id is None or not sketch_element:
            return
        entity = sketch_element.sketch.registry.get_entity(
            self._text_entity_id
        )
        if not isinstance(entity, TextBoxEntity):
            return
        cmd = ModifyTextPropertyCommand(
            sketch=sketch_element.sketch,
            text_entity_id=self._text_entity_id,
            new_content=entity.content + "{serial()}",
            new_font_config=entity.font_config,
        )
        self.editor.history_manager.execute(cmd)
```

- [ ] **Step 6: Lint, then run the tests**

Run: `pixi run lint`
Expected: no errors.
Run: `pixi run uitest rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_serial_settings.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/serial_settings.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/frontend.py rayforge/builtin_addons/rayforge-addon-sketcher/sketcher/ui_gtk/font_properties.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_serial_settings.py rayforge/builtin_addons/rayforge-addon-sketcher/tests/ui_gtk/test_font_properties.py
git commit -m "feat(sketcher): serial number settings page"
```

---

### Task 23: English user and developer docs (Phase 8)

Executor tier: ANTIGRAVITY-LOW
Depends on: Tasks 5, 7, 11, 17, 18, 20, 22 (document only what has landed; the **Custom Fonts** section additionally needs Task 15)
Parallel-safe with: Task 25, 26

**Files:**

- Modify: `website/docs/features/sketcher/text-box.md` (after the `## Font Properties` section, `:26-35`)
- Modify: `website/docs/features/sketcher/expressions.md` (built-in table `:109-118`, custom function intro `:124-127`)
- Modify: `website/docs/developer/addon-hooks.md` (after `main_window_ready` `:65-78`, version history `:281-290`)

Read `docs/agents/website.md` first. There is no automated test for
markdown; the check is `pixi run site-format` leaving the files formatted.

**Interfaces:**

- Consumes: the UI labels exactly as written in Tasks 5, 7, 11, 15, 17, 22.
- Produces: the English source pages Task 24 translates.

- [ ] **Step 1: Extend `text-box.md`**

Replace the three bullets under `## Font Properties` with:

```markdown
- **Font family** — choose from the installed system fonts.
- **Custom font** — choose a font you installed yourself (see
  [Custom Fonts](#custom-fonts)).
- **Font size** — in points.
- **Bold** and **Italic** toggles.
```

Insert these sections directly before `## A Parametric Frame`:

```markdown
## Text Transforms

The same panel can change how the text is laid out inside its frame:

- **Mirror** — flips the text left to right, for engraving the back of a
  transparent material.
- **Reverse Characters** — writes the characters in reverse order without
  flipping them.
- **Vertical** — stacks upright characters from top to bottom.
- **Rotation** — turns the text around the centre of its frame. The frame
  itself stays horizontal.
- **Upside Down** — a shortcut for a rotation of 180°.

While one of these is active you can still type into the text box, but
clicking no longer places the caret inside the text.

## Knock-out Text

Turn on **Knock-out** to engrave a plate with the text left blank. The plate
is the text frame grown by the **Knock-out Margin** on every side. The
outline contains the plate and the letters; the fill covers the plate except
for the letters.

The enclosed parts of letters such as O, A and B are not kept, so knock-out
text is meant for engraving, not for cutting stencils.

## Text on a Path

Text can follow a line, an arc, a circle or a curve:

1. Select the text box together with the shape it should follow.
2. Activate **Follow Path** in the Font Properties panel.

- **Path Side** — **Outside** places the text on the left of the path
  direction; **Inside** places it on the other side and reverses the reading
  direction, so text on the inside of a circle reads upright at the bottom.
- **Path Alignment** — start, centre or end of the path.
- **Path Offset** — shifts the text along the path.
- **Bottom Text** — on a circle, a second line of text that is centred at
  the bottom on the inside, while the main text is centred at the top on the
  outside. Both read upright, which makes a round stamp or seal.

To release the text, select only the text box and activate **Follow Path**
again. If the shape is deleted, the text returns to its frame.

Text on a path keeps its font size, and mirror, vertical, rotation and
knock-out do not apply to it. A path is a single shape; text does not
continue from one line or arc onto the next.

## Custom Fonts

Use **Install Font…** to add a `.ttf` or `.otf` file. Installed fonts appear
in the **Custom Font** list on every sketch, and **Remove Custom Font**
deletes the selected one.

Fonts are stored on your computer, not inside the project file. When a
project uses a font that is not installed, the panel shows **Font Not
Installed** and a substitute font is used until you install the font or pick
another one.

## Presets

A preset stores the font and the text style, but not the text itself or the
path it follows. Type a name into **Save as Preset** to store the settings of
the selected text box, pick a name from **Preset** to apply it, and use
**Delete Preset** to remove the selected preset. Applying a preset is a
single undo step.

## Serial Numbers

**Insert Serial Number** adds `{serial()}` to the text. It shows the current
value of a counter, and the counter moves on by one step each time a job is
sent to the machine or exported as G-code. Framing, previews and cancelled or
failed jobs do not use up a number.

Counters are shared by all documents and are managed under **Settings →
Serial Numbers**, where each counter has a start value, step, zero padding,
prefix and suffix. Use `{serial("name")}` to show a specific counter.
```

- [ ] **Step 2: Extend `expressions.md`**

Add a row at the end of the built-in table (after the `{uuid()}` row):

```markdown
| `{serial()}`    | `str`       | Current value of a serial counter; `{serial("name")}` selects one |
```

Directly below the table's following paragraph ("Typical uses include…"),
add:

```markdown
`serial()` reads a persistent counter that advances once for every job that
is sent or exported, so every part gets the next number. See
[Serial Numbers](text-box.md#serial-numbers).
```

In `## Custom template functions`, add this sentence at the end of the
introductory paragraph (the one mentioning serial numbers from a database):

```markdown
For a simple running number you do not need a script: use the built-in
`serial()` function.
```

- [ ] **Step 3: Extend `addon-hooks.md`**

Insert after the `main_window_ready` section (before `## Registration Hooks`):

```markdown
### `job_dispatched(doc, kind)`

Called on the main thread after a job was handed off successfully. `kind` is
`"send"` when the machine ran a sent job and `"export"` when G-code was
written to a file. Framing, pointer dry runs, failed or empty jobs, sanity
checks and previews do not call it. Use it for anything that should happen
once per produced part, such as advancing a counter.

```python
@hookimpl
def job_dispatched(doc, kind):
    logger.info(f"Job dispatched ({kind}) with {len(doc.all_workpieces)} items")
```
```

In `## API Version History`, change `The current API version is 9.` to
`The current API version is 22.` and insert above the `**Version 9**`
paragraph:

```markdown
**Version 22** added `job_dispatched`.
```

`website/docs/developer/addon-manifest.md` uses `api_version: 9` only as an
example value; leave it unchanged.

- [ ] **Step 4: Format and review**

Run: `pixi run site-format`
Expected: exits 0.
Run: `git diff --stat website/docs`
Expected: only the three files above changed.

- [ ] **Step 5: Commit**

```bash
git add website/docs/features/sketcher/text-box.md website/docs/features/sketcher/expressions.md website/docs/developer/addon-hooks.md
git commit -m "docs: text transforms, round text, fonts, presets and serials"
```

---

### Task 24: Translated docs (Phase 8)

Executor tier: ANTIGRAVITY-LOW
Depends on: Task 23
Parallel-safe with: Task 25, 26

**Files (for each `<lang>` in `de es fr hi pt-BR uk zh-CN`):**

- Modify: `website/i18n/<lang>/docusaurus-plugin-content-docs/current/features/sketcher/text-box.md`
- Modify: `website/i18n/<lang>/docusaurus-plugin-content-docs/current/features/sketcher/expressions.md`
- Modify: `website/i18n/<lang>/docusaurus-plugin-content-docs/current/developer/addon-hooks.md` (only where the file exists)

**Interfaces:**

- Consumes: the English text added in Task 23.
- Produces: the same sections in every translated page.

- [ ] **Step 1: List what must be translated**

Run: `git show --stat HEAD -- website/docs` (the Task 23 commit) and
`git show HEAD -- website/docs` to see the exact English additions.
Run: `ls website/i18n/*/docusaurus-plugin-content-docs/current/developer/addon-hooks.md`
Expected: the list of languages that have a translated hooks page; skip the
others for that file.

- [ ] **Step 2: Translate, one language at a time**

For each language, add the same sections at the same positions as in the
English pages, translated into that language. Rules:

- Keep code, template expressions (`{serial()}`, `{serial("name")}`), file
extensions and anchors' target files unchanged.
- UI labels (**Mirror**, **Follow Path**, **Knock-out**, …) must match the
catalog translation from Task 25 for that language; if Task 25 has not
landed, use the translation you will put in the catalog and note it in
the task report so Task 25 uses the same wording.
- Keep heading levels and list structure identical to the English page.

- [ ] **Step 3: Verify every page got every section**

Run:

```bash
for f in website/i18n/*/docusaurus-plugin-content-docs/current/features/sketcher/text-box.md; do echo "$f $(grep -c '^## ' "$f")"; done
grep -c '^## ' website/docs/features/sketcher/text-box.md
```

Expected: every translated file reports the same number of `##`  headings
as the English file.

Run:

```bash
grep -L "serial()" website/i18n/*/docusaurus-plugin-content-docs/current/features/sketcher/expressions.md
```

Expected: no output (every translated expressions page mentions `serial()`).

- [ ] **Step 4: Format and commit**

Run: `pixi run site-format`
Expected: exits 0.

```bash
git add website/i18n
git commit -m "docs(i18n): translate text feature documentation"
```

---

### Task 25: gettext catalogs (Phase 8)

Executor tier: ANTIGRAVITY-LOW
Depends on: Tasks 5, 7, 11, 17, 22 (and Task 15 for the custom font strings)
Parallel-safe with: Task 23, 24, 26

**Files:**

- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/locale/sketcher.pot`
- Modify: `rayforge/builtin_addons/rayforge-addon-sketcher/locale/<lang>/LC_MESSAGES/sketcher.po` for `<lang>` in `de en es fr hi pt uk zh_CN`

Read `docs/agents/translations.md` first. Append entries; never regenerate
the catalogs (`pixi run update-translations` rewrites every catalog in the
repository and must not be used here). The core catalog under
`rayforge/locale` needs no change: Task 18 adds no user-visible string.

**Interfaces:**

- Consumes: every `_()` string added by Tasks 5, 7, 11, 15, 17 and 22.
- Produces: catalog entries for those strings in the template and all
eight language catalogs.

- [ ] **Step 1: Collect the new message ids**

Run: `pixi run print-untranslated list`
Expected: the sketcher catalog lists the new strings as missing. The
complete set is:

From `sketcher/ui_gtk/font_properties.py`:
`Mirror`, `Reverse Characters`, `Vertical`, `Upside Down`, `Rotation`,
`Knock-out`, `Knock-out Margin`, `Follow Path`, `Path Side`, `Outside`,
`Inside`, `Path Alignment`, `Start`, `Center`, `End`, `Path Offset`,
`Bottom Text`, `Bind the text to the selected shape`,
`Following a path. Activate to release`,
`Select the text box together with a line, arc, circle or curve`,
`Font Not Installed`,
`A substitute font is used. Install the font or pick another.`,
`Custom Font`, `Install Font…`, `Remove Custom Font`, `None`,
`Could not install {name}`, `Font Files`, `Install Font`, `Preset`,
`Save as Preset`, `Delete Preset`, `Choose…`, `Insert Serial Number`,
`Counters are managed in Settings`.

From `sketcher/ui_gtk/serial_settings.py`:
`Serial Numbers`,
`Counters advance once for every job sent to the machine or exported. Use them in a text box with {serial("name")}.`,
`New Counter Name`, `Current Value`, `Start`, `Step`, `Zero Padding`,
`Prefix`, `Suffix`, `Reset to Start`, `Delete Counter`.

A message id that already exists in the catalog (for example `None`,
`Start` or `Center`) must not be added a second time: add the new
`#: sketcher/...` reference line to the existing entry instead. Check each
with:

```bash
grep -n '^msgid "Start"$' rayforge/builtin_addons/rayforge-addon-sketcher/locale/sketcher.pot
```

- [ ] **Step 2: Append to the template**

Append one entry per new message id to
`rayforge/builtin_addons/rayforge-addon-sketcher/locale/sketcher.pot`, in
this form:

```
#: sketcher/ui_gtk/font_properties.py
msgid "Mirror"
msgstr ""

#: sketcher/ui_gtk/font_properties.py
#, python-brace-format
msgid "Could not install {name}"
msgstr ""
```

Only `Could not install {name}` carries a named placeholder and gets the
`#, python-brace-format` flag. The serial settings description contains
literal braces that are not placeholders (`{serial("name")}`); do not flag
it.

- [ ] **Step 3: Append to every language catalog**

For each of `de en es fr hi pt uk zh_CN`, append the same entries to
`locale/<lang>/LC_MESSAGES/sketcher.po` with the translation in `msgstr`.
The `en` catalog keeps `msgstr ""`. Keep `{name}` unchanged in every
translation. Example for `de`:

```
#: sketcher/ui_gtk/font_properties.py
msgid "Mirror"
msgstr "Spiegeln"

#: sketcher/ui_gtk/font_properties.py
#, python-brace-format
msgid "Could not install {name}"
msgstr "{name} konnte nicht installiert werden"
```

- [ ] **Step 4: Validate**

Run:

```bash
for f in rayforge/builtin_addons/rayforge-addon-sketcher/locale/*/LC_MESSAGES/sketcher.po; do msgfmt --check --check-format -o /dev/null "$f" || echo "FAILED $f"; done
```

Expected: no `FAILED` line and no duplicate-message error.
Run: `git diff --stat rayforge/builtin_addons/rayforge-addon-sketcher/locale`
Expected: insertions only (0 deletions) in nine files.
Run: `pixi run print-untranslated list`
Expected: the sketcher catalog no longer lists the strings from Step 1
(except in `en`, which is expected to stay empty).

- [ ] **Step 5: Commit**

```bash
git add rayforge/builtin_addons/rayforge-addon-sketcher/locale
git commit -m "i18n(sketcher): translate text feature strings"
```

---

### Task 26: Refresh the font properties screenshot (Phase 8)

Executor tier: ANTIGRAVITY-LOW
Depends on: Tasks 5, 7, 11, 17, 22 (the panel must have its final rows)
Parallel-safe with: Task 23, 24, 25

**Files:**

- Regenerate: the image served as `/screenshots/addons-sketcher-tool-text-box-font-properties.webp` (referenced at `website/docs/features/sketcher/text-box.md:28`)
- No source change: `scripts/screenshot/sketcher_tools.py` already captures
this panel.

**Interfaces:**

- Consumes: the finished Font Properties panel.
- Produces: an up-to-date screenshot for the docs.

- [ ] **Step 1: Find where the current image lives**

Run: `git ls-files | grep "addons-sketcher-tool-text-box"`
Expected: the tracked path(s) of the text box screenshots.

- [ ] **Step 2: Regenerate**

Run: `pixi run screenshot addons:sketcher:tool:text-box:font-properties`
Run: `pixi run screenshot addons:sketcher:tool:text-box`
Expected: both commands exit 0 and rewrite the files found in Step 1.
(The screenshot task needs a display; on a headless Linux host run it
under `xvfb-run -a`.)

- [ ] **Step 3: Check the result**

Open the regenerated font properties image and confirm it shows the new
rows (Preset, Mirror, Rotation, Knock-out, Follow Path, Insert Serial
Number). The panel is taller than before; if the capture is cut off, the
crop is defined in `scripts/screenshot/sketcher_tools.py`: report that to
the coordinator rather than changing the script here.

Run: `git status --short`
Expected: only the screenshot files from Step 1 are modified.

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "docs: refresh text box screenshots"
```

---

## Self-Review

**Spec coverage**


| Spec item                                                                    | Task                                      |
| ---------------------------------------------------------------------------- | ----------------------------------------- |
| Decision 1, rotation on the text box, frame keeps its constraint             | 2, 4                                      |
| Decision 2, knock-out plate is the frame plus margin                         | 6, 7                                      |
| Decision 3, `job_dispatched(doc, kind)`, API 21 to 22                        | 18                                        |
| Decision 4, advance after a successful hand-off; export counts               | 18, 21                                    |
| Decision 5, global counters, file re-read on advance                         | 19                                        |
| Decision 6, Settings page via `register_settings_pages`                      | 22                                        |
| Decision 7, separate Custom font list, install and remove                    | 15                                        |
| Decision 8, missing-font warning, fonts not embedded                         | 15                                        |
| Decision 9, single-entity paths                                              | 10                                        |
| Decision 10, bottom text field on one text box                               | 10, 11                                    |
| Decision 11, raygeo `load_font_file` in a separate PR, then pin bump         | 12, 13                                    |
| Data model, eleven attributes, non-default serialization, `FORMAT_VERSION` 1 | 2                                         |
| `geometry_signature` and `rewrite_offsets_from` include style                | 2, 10                                     |
| `ModifyTextPropertyCommand` style snapshot                                   | 3                                         |
| Geometry order: reverse, layout, mirror, `map_to_frame`, rotate              | 4                                         |
| Knock-out via `get_polygons_group_difference`                                | 6                                         |
| `text_on_path` helper; `curve_along` Circle support, public helpers          | 8, 9                                      |
| Canvas uses `entity.to_geometry`                                             | 1                                         |
| Caret placement disabled for transformed text                                | 5                                         |
| `core/fonts.py`, loaded in `worker.py` and `frontend.py`                     | 14                                        |
| `core/text_presets.py`, atomic writes, applied through the command           | 16, 17                                    |
| `core/serial.py`, `{serial("name")}` never advances                          | 19, 20                                    |
| Refresh on dispatch and on `document_changed`                                | 21                                        |
| Hook call sites in `_run_send_action` and `export_gcode_to_path`             | 18                                        |
| Docs, translations, screenshots                                              | 23, 24, 25, 26                            |
| Open item: pipeline subprocesses and `rayforge_init`                         | 14 (also loads in `register_asset_types`) |
| Open item: swash licence                                                     | 12, Step 6                                |
| Open item: minimum Pango                                                     | closed by decision 7 (15)                 |


**Deviations from the spec text, on purpose**

- Caret placement is also disabled for `reverse` and path-bound text, not
only mirror, vertical and rotation: clicks would land on the wrong
character there too (Task 5).
- The two arc-length helpers live in a new `core/polyline.py` and are
re-exported from `curve_along`, instead of only being renamed in place;
this avoids an import cycle between `entities` and `arrays` (Task 8).
- Deleting a bound path entity does not clear `path_entity_id`; the text
falls back to its frame while the id dangles. Entity ids are never
reused, and this keeps undo of the delete correct (Task 10).
- The knock-out plate rotates with the text (Task 6), and knock-out,
mirror, vertical and rotation are ignored for path-bound text (Task 10).
- Fonts are additionally loaded in `register_asset_types` (Task 14).
- **Follow Path** binds through a combined selection (text box plus one
shape) handled in `studio.py`, since the panel was only shown for a
single selected text box (Task 11).

**Type consistency check**

- `STYLE_DEFAULTS`, `get_style`, `set_style` (Task 2) are used with the same
names in Tasks 3, 5, 7, 10, 11, 16, 17.
- `new_style` keyword (Task 3) is used in Tasks 5, 17; `apply_font_change(new_font_config, new_style=None)` (Task 5) matches its caller in the same task.
- `_frame_glyphs` (Task 4) is redefined with the same signature in Task 6
and wrapped by `_glyphs` in Task 10; `get_plate_ring` and
`to_fill_geometry` (Task 6) keep their signatures in Task 10.
- `cumulative_lengths`, `point_at_arclength`, `polyline_for` (Task 8) match
their use in Task 9; `text_on_path(text, font_config, polyline, side, align, offset)`
(Task 9) matches both calls in Task 10.
- `load_font_file(path: str) -> list[str]` (Task 12) matches its use in
Task 14; `install_font`, `remove_font`, `list_custom_families`,
`is_custom_family`, `is_known_family` (Tasks 14, 15) match the widget.
- `TextPreset`, `preset_from_entity`, `load_presets`, `save_preset`,
`delete_preset`, `presets_path` (Task 16) match Task 17 and its tests.
- `SerialCounter`, `load_counters`, `save_counters`, `peek`, `advance`,
`find_serial_names`, `serials_path`, `DEFAULT_NAME` (Task 19) match
Tasks 20, 21, 22.
- `job_dispatched(doc, kind)` (Task 18) matches the hookimpl in Task 21.

**Assumptions that could not be verified while writing this plan**

raygeo is not installed in this worktree and `pixi` is not available on the
planning host, so no code or test in this plan was executed. Signatures were
checked against the Rayforge sources and against raygeo `v1.63.0` (type
stubs and Rust sources on GitHub). The points that rest on reading rather
than running:

1. `Geometry.transform` mutates in place (it is used that way in
 `SK/image/renderer.py:92`); the plan relies on that.
2. The rotation direction of `Matrix.rotation` (assumed counter-clockwise
 for positive degrees, Y up). Tasks 4 and 9 carry a note on what to do if
 the tests show the opposite.
3. `Geometry.rect()` on an empty geometry returns zeros rather than
 raising (the existing code already calls it for blank text).
4. `Entity.to_polyline` returns arcs and Beziers start-first; Task 10 has a
 test that pins this and a fallback instruction.
5. `driver.run` raises, rather than returning normally, when a job is
 cancelled or fails mid-way. If a driver returns normally on cancel, that
 job would advance the serial; this is driver behaviour outside this plan
 and should be checked per driver during review of Task 18.
6. The `when_done` callback of `generate_job_artifact` runs on the main
 thread (it already sends UI notifications directly).
7. `SpinRow.value_changed.connect` accepting extra positional arguments
 (Task 22 gives the `partial` alternative).
8. `JobArtifact` accepting `encoded_output=None` with empty `Ops` in the
 Task 18 test (alternative given in that task).
9. UI tests need Linux with xvfb (`pixi run uitest`); they cannot run on a
 macOS executor.
10. The icon names `warning-symbolic` and `view-list-symbolic` resolve in
 the app's icon set (`warning-symbolic` is used by the tool library
 addon; `view-list-symbolic` is a standard Adwaita icon).
11. The test font: Tasks 12 and 14 need one OFL-licensed `.ttf` whose
 family name is not a common system font; the file itself has to be
 downloaded by the executor.