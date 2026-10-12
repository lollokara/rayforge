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

_SERIAL_CALL = re.compile(r"""(?<![\w.])serial\(\s*(?:(["'])(.*?)\1)?\s*\)""")
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
        match.group(2) or DEFAULT_NAME for match in _SERIAL_CALL.finditer(text)
    }
