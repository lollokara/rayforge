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
