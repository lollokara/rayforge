"""
Frontend entry point for sketcher addon.

Registers UI widgets with the main application.
"""

import logging

from rayforge.core.hooks import hookimpl

from .core.serial_dispatch import on_job_dispatched, refresh_serials

logger = logging.getLogger(__name__)

ADDON_NAME = "sketcher"

_doc_editor = None


def _on_document_changed(editor, **kwargs):
    """Refresh serial numbers cached in a newly loaded document."""
    refresh_serials(editor.doc)


@hookimpl
def job_dispatched(doc, kind):
    """Advance the serial counters used by the dispatched document."""
    on_job_dispatched(doc)


@hookimpl
def register_commands(command_registry):
    """Register SketchCmd with the command registry."""
    from .ui_gtk.sketch_cmd import SketchCmd

    command_registry.register("sketch", SketchCmd, ADDON_NAME)


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
