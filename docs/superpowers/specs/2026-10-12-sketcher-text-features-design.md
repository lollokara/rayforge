# Sketcher text box extension: design

Date: 2026-10-12
Status: draft, awaiting review
Basis: read-only plan `sketcher-text-box-plan.md` (Opus worker, run
`run_f1bb79b4b8ad`) plus the decisions below.

## Intent

Let a user produce laser-ready text in the build volume from the existing
Sketcher Text Box tool (`G+T`), with custom fonts, saved presets, persistent
serial numbers, text transforms and round text. Extend the builtin sketcher
addon; do not create a separate addon.

## Decisions

| # | Topic | Decision |
|---|---|---|
| 1 | Rotation | Angle stored on the text box; frame keeps its horizontal constraint |
| 2 | Knock-out plate | Text frame grown by a margin |
| 3 | Job-run surface | New public hook `job_dispatched(doc, kind)`; `PLUGIN_API_VERSION` 21 to 22 |
| 4 | Serial advance | After a send is handed to the machine successfully; G-code export counts; cancelled or failed jobs do not |
| 5 | Counter scope | Global, shared; the file is re-read on every advance |
| 6 | Serial settings UI | Global Settings page via `register_settings_pages` |
| 7 | Custom fonts in picker | Separate "Custom font" list with Install and Remove |
| 8 | Font portability | Missing-font warning; fonts are not embedded in projects |
| 9 | Path scope | Single entity: line, arc, circle or Bezier |
| 10 | Ring layout | One text box with a second "bottom text" field |
| 11 | raygeo | Add `load_font_file` in a separate raygeo PR, then bump the pin |

Out of scope: batch or array serial mode, chained multi-segment paths,
embedding fonts, single-line (Hershey) fonts.

## Design

### Data model
`TextBoxEntity` gains `mirror`, `reverse`, `vertical`, `rotation`, `knockout`,
`knockout_margin`, `path_entity_id`, `path_side`, `path_offset`, `path_align`
and `content_bottom`. They serialize only when non-default and load with
`data.get`, so old files load unchanged and `FORMAT_VERSION` stays 1. They are
not stored in `FontConfig.extra`, which drops non-string values on copy.
`geometry_signature` and `rewrite_offsets_from` include them.
`ModifyTextPropertyCommand` carries an optional style snapshot so changes are
undoable.

### Geometry
Fixed order in `TextBoxEntity.to_geometry`: reverse characters, lay out
(vertical stacks upright characters), mirror, `map_to_frame`, rotate about the
frame centre. Upside-down is `rotation = 180`.

Knock-out produces a plate ring (frame plus margin) and fills as plate minus
glyphs through `get_polygons_group_difference`.

Round text lives in a new `text_on_path` helper. It places each character from
`FontConfig.get_text_position` at its arc length, rotated to the tangent.
Inside text flips the normal and reading direction. With a circle and
`content_bottom`, the top string is centred outside and the bottom string
inside, both upright. `curve_along` gains `Circle` support and its three
sampling helpers become public.

The canvas path `SketchRenderer._define_text_box_path` is replaced by
`entity.to_geometry` so canvas and output cannot diverge.

Caret placement is disabled while mirror, vertical or rotation is active;
typing still works.

### Fonts
raygeo gets `load_font_file(path) -> list[str]` (`font_database()` becomes an
`RwLock`). The sketcher adds `core/fonts.py` to install, remove, list and load
fonts under `get_addon_data_dir("sketcher")/fonts`, loaded in `rayforge_init`
of both `worker.py` and `frontend.py` so job geometry uses the same faces. The
Font Properties widget shows a warning when the family is not installed.

### Presets
`core/text_presets.py` stores name, font config and style (no content, no path
binding) in `text_presets.json`, written atomically. Applying goes through
`ModifyTextPropertyCommand`.

### Serial numbers
`core/serial.py` holds `SerialCounter` (name, value, start, step, padding,
prefix, suffix) persisted in `serials.json`. `{serial("name")}` returns the
current formatted value and never advances. On `job_dispatched` the sketcher
advances each counter used by the document once, then calls
`WorkPiece.regenerate_from_geometry_provider()` on the affected workpieces. The
same refresh runs on `DocEditor.document_changed`, because resolved text is
cached per workpiece and saved in the project. The hook is called from
`MachineCmd._run_send_action` after `driver.run` returns (not for framing,
`pointer_dry_run` or failures) and from `FileCmd.export_gcode_to_path` after the
write. Sanity checks and previews do not count.

## Delivery

Phases, each independently shippable and test-first with targeted tests only
(lint clean before any wider run):

0. Remove the duplicate glyph path.
1. Style data model and command snapshot.
2. Transforms.
3. Knock-out.
4. Round text and ring layout.
5. Custom fonts (needs the raygeo release).
6. Presets.
7. Serial numbers and the `job_dispatched` hook.
8. Docs, translations, screenshots.

Phases 0 to 4 are sequential sketcher work. Phase 7 is independent and may go
first. Phase 5 waits on raygeo.

### Execution method (requested by the user)
Run through Orca-supervised subagents: Antigravity at low effort for easy edits
(docs, translations, catalogs, mechanical renames), Sonnet for harder work
(geometry, commands, hook, serial logic). The coordinator checks quota between
waves, if the Orca CLI exposes it, and pauses before any account runs dry.
The implementation plan will assign each task to a tier. This is not approved
for execution until the plan is reviewed.

## Risks
- Duplicate serials from the persisted text cache: covered by the load-time
  refresh and an explicit test.
- Worker subprocesses without custom fonts: load fonts in the worker entry; the
  worker report did not confirm that pipeline subprocesses call `rayforge_init`.
- raygeo release coupling, and the `RwLock` change on a per-keystroke path.
- Knock-out drops counters of O, A, B (no bridges): acceptable for engraving.
- Degraded editing on rotated, vertical and path text.
- Per-character layout cost for path and vertical text.

## Open items to verify during planning
- Whether pipeline subprocesses call `rayforge_init`.
- Exact `swash` licence in raygeo's `Cargo.lock`.
- Minimum Pango on snap and Debian (not needed with the separate font list).
