import logging
from gettext import gettext as _
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gi.repository import Adw, Gio, GLib, Gtk, Pango
from raygeo.geo.shape.text import FontConfig

from rayforge.ui_gtk.icons import get_icon
from rayforge.ui_gtk.shared.pref_rows import (
    AngleSpinRow,
    LengthSpinRow,
    SpinRow,
)

from ..core import fonts, text_presets
from ..core.commands.text_property import (
    ModifyTextPropertyCommand,
)
from ..core.entities import Arc, Bezier, Circle, Line
from ..core.entities.text_box import TextBoxEntity

if TYPE_CHECKING:
    from .editor import SketchEditor

logger = logging.getLogger(__name__)

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


class FontPropertiesWidget(Adw.PreferencesGroup):
    """
    A widget that displays font properties for a selected TextBoxEntity.
    Shows font family, size, bold, and italic options using Adw widgets.
    """

    def __init__(self, editor: "SketchEditor"):
        super().__init__()
        self.editor = editor
        self._text_entity_id: int | None = None
        self._in_update = False
        self._current_font_family = "sans-serif"
        self._presets: list[text_presets.TextPreset] = []
        self._path_candidate_id: int | None = None
        self._path_entity_id: int | None = None

        self.set_title(_("Font Properties"))
        self.set_description(
            _("Configure font family, size, and style for text boxes")
        )
        self.set_visible(False)

        self._build_ui()

    def _build_ui(self):
        """Builds the UI for font properties."""
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

        self.font_family_row = Adw.ActionRow()
        self.font_family_row.set_title(_("Font Family"))
        self.font_family_row.set_subtitle(self._current_font_family)
        self.font_family_row.set_activatable(True)
        self.font_family_row.connect(
            "activated", self._on_font_family_row_activated
        )
        self.font_family_row.add_suffix(get_icon("go-next-symbolic"))
        self.add(self.font_family_row)

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

        self.font_size_row = SpinRow(
            _("Font Size"),
            lower=1.0,
            upper=500.0,
            step_increment=0.1,
            digits=1,
            value=10.0,
        )
        self.font_size_row.value_changed.connect(self._on_font_size_changed)
        self.add(self.font_size_row)

        self.bold_row = Adw.ActionRow()
        self.bold_row.set_title(_("Bold"))

        bold_switch = Gtk.Switch()
        bold_switch.set_valign(Gtk.Align.CENTER)
        bold_switch.connect("state-set", self._on_bold_changed)
        self.bold_row.add_suffix(bold_switch)
        self.bold_row.set_activatable_widget(bold_switch)
        self.bold_switch = bold_switch
        self.add(self.bold_row)

        self.italic_row = Adw.ActionRow()
        self.italic_row.set_title(_("Italic"))

        italic_switch = Gtk.Switch()
        italic_switch.set_valign(Gtk.Align.CENTER)
        italic_switch.connect("state-set", self._on_italic_changed)
        self.italic_row.add_suffix(italic_switch)
        self.italic_row.set_activatable_widget(italic_switch)
        self.italic_switch = italic_switch
        self.add(self.italic_row)

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

        self.knockout_switch = self._add_switch_row(
            _("Knock-out"), self._on_style_changed
        )

        self.knockout_margin_row = LengthSpinRow(
            _("Knock-out Margin"),
            lower=0.0,
            upper=1000.0,
            value_in_base=2.0,
        )
        self.knockout_margin_row.value_changed.connect(self._on_style_changed)
        self.add(self.knockout_margin_row)

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
        self.path_align_row.connect("notify::selected", self._on_style_changed)
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

        if entity_id is None:
            self.set_visible(False)
            return

        sketch_element = self.editor.sketch_element
        if not sketch_element:
            self.set_visible(False)
            return

        entity = sketch_element.sketch.registry.get_entity(entity_id)
        if not isinstance(entity, TextBoxEntity):
            self.set_visible(False)
            return

        self.set_visible(True)
        self._update_ui_from_model(entity.font_config)
        self._update_style_ui(entity)
        self._refresh_presets()

    def _update_ui_from_model(self, font_config: FontConfig):
        """Updates the UI widgets from the font configuration."""
        self._in_update = True
        try:
            self.font_size_row.set_value(font_config.size)
            self.bold_switch.set_active(font_config.bold)
            self.italic_switch.set_active(font_config.italic)
            self._current_font_family = font_config.family
            self.font_family_row.set_subtitle(self._current_font_family)
            self._refresh_custom_fonts()
        finally:
            self._in_update = False

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

    def _get_font_config_from_ui(self) -> FontConfig:
        """Creates a FontConfig from the current UI values."""
        return FontConfig(
            family=self._current_font_family,
            size=self.font_size_row.get_value(),
            bold=self.bold_switch.get_active(),
            italic=self.italic_switch.get_active(),
        )

    def _update_style_ui(self, entity: TextBoxEntity):
        """Updates the style widgets from the text entity."""
        self._in_update = True
        try:
            self.mirror_switch.set_active(entity.mirrored)
            self.reverse_switch.set_active(entity.reverse)
            self.vertical_switch.set_active(entity.vertical)
            self.rotation_row.set_value(entity.rotation)
            self.upside_down_switch.set_active(entity.rotation == 180.0)
            self.knockout_switch.set_active(entity.knockout)
            self.knockout_margin_row.set_value_in_base_units(
                entity.knockout_margin
            )
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
        finally:
            self._in_update = False

    def _get_style_from_ui(self) -> dict[str, Any]:
        """Collects the style values shown by the widget."""
        return {
            "mirrored": self.mirror_switch.get_active(),
            "reverse": self.reverse_switch.get_active(),
            "vertical": self.vertical_switch.get_active(),
            "rotation": self.rotation_row.get_value(),
            "knockout": self.knockout_switch.get_active(),
            "knockout_margin": (
                self.knockout_margin_row.get_value_in_base_units()
            ),
            "path_entity_id": self._path_entity_id,
            "path_side": _PATH_SIDES[self.path_side_row.get_selected()],
            "path_align": _PATH_ALIGNS[self.path_align_row.get_selected()],
            "path_offset": self.path_offset_row.get_value_in_base_units(),
            "content_bottom": self.bottom_text_row.get_text(),
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

    def _on_insert_serial_activated(self, row, *args):
        """Appends the default serial-number template to the text."""
        entity = self._text_entity()
        sketch_element = self.editor.sketch_element
        if entity is None or not sketch_element:
            return
        cmd = ModifyTextPropertyCommand(
            sketch=sketch_element.sketch,
            text_entity_id=entity.id,
            new_content=entity.content + "{serial()}",
            new_font_config=entity.font_config,
        )
        self.editor.history_manager.execute(cmd)

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
        sketch_element = self.editor.sketch_element
        if not sketch_element:
            return
        entity = self._text_entity()
        if entity is None:
            return
        cmd = ModifyTextPropertyCommand(
            sketch=sketch_element.sketch,
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

    def _on_font_family_row_activated(self, row, *args):
        """Handles font family row activation to open font chooser."""
        if self._in_update or self._text_entity_id is None:
            return
        self._open_font_chooser_dialog()

    def _on_font_size_changed(self, row):
        """Handles font size change."""
        if self._in_update or self._text_entity_id is None:
            return
        self._apply_font_config()

    def _on_bold_changed(self, switch, state):
        """Handles bold toggle change."""
        if self._in_update or self._text_entity_id is None:
            return
        self._apply_font_config()

    def _on_italic_changed(self, switch, state):
        """Handles italic toggle change."""
        if self._in_update or self._text_entity_id is None:
            return
        self._apply_font_config()

    def _open_font_chooser_dialog(self):
        """Opens a Gtk font chooser dialog for font selection."""
        dialog = Gtk.FontChooserDialog(
            title=_("Select Font"), transient_for=self.editor.parent_window
        )
        font_desc = self._get_font_description_from_ui()
        dialog.set_font_desc(font_desc)

        def on_response(dialog, response):
            logger.debug(f"Font chooser dialog response: {response}")
            if response == Gtk.ResponseType.OK:
                font_desc = dialog.get_font_desc()
                logger.debug(f"Selected font description: {font_desc}")
                if font_desc is not None:
                    self._update_ui_from_font_description(font_desc)
                    self._apply_font_config()
            dialog.destroy()

        dialog.connect("response", on_response)
        dialog.present()

    def _get_font_description_from_ui(self) -> Pango.FontDescription:
        """Creates a Pango.FontDescription from current UI values."""
        font_desc = Pango.FontDescription()
        font_desc.set_family(self._current_font_family)
        font_size_pt = self.font_size_row.get_value()
        font_desc.set_size(int(font_size_pt * Pango.SCALE))
        style = (
            Pango.Style.ITALIC
            if self.italic_switch.get_active()
            else Pango.Style.NORMAL
        )
        font_desc.set_style(style)
        weight = (
            Pango.Weight.BOLD
            if self.bold_switch.get_active()
            else Pango.Weight.NORMAL
        )
        font_desc.set_weight(weight)
        return font_desc

    def _update_ui_from_font_description(
        self, font_desc: Pango.FontDescription
    ):
        """Updates UI widgets from a Pango.FontDescription."""
        self._in_update = True
        try:
            family = font_desc.get_family()
            if family:
                self._current_font_family = family
                self.font_family_row.set_subtitle(self._current_font_family)
                self._refresh_custom_fonts()

            size = font_desc.get_size()
            if size > 0:
                font_size_pt = size / Pango.SCALE
                self.font_size_row.set_value(font_size_pt)

            style = font_desc.get_style()
            is_italic = style == Pango.Style.ITALIC
            self.italic_switch.set_active(is_italic)

            weight = font_desc.get_weight()
            is_bold = weight >= Pango.Weight.BOLD
            self.bold_switch.set_active(is_bold)
        finally:
            self._in_update = False

    def _apply_font_config(self):
        """Applies the current font configuration to the text entity."""
        if self._text_entity_id is None:
            return

        sketch_element = self.editor.sketch_element
        if not sketch_element:
            return

        entity = sketch_element.sketch.registry.get_entity(
            self._text_entity_id
        )
        if not isinstance(entity, TextBoxEntity):
            return

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
