"""Settings page for the global serial-number counters."""

import logging
from functools import partial
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
                partial(self._on_int_changed, name=counter.name, field=field)
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

    def _on_int_changed(self, row, *, name: str, field: str) -> None:
        self.update_counter(name, **{field: row.get_int_value()})

    def _on_text_applied(self, row, name: str, field: str) -> None:
        self.update_counter(name, **{field: row.get_text()})
