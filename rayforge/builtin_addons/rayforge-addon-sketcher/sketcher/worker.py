"""
Backend entry point for sketcher addon.

Registers asset types and renderers with the main application.
"""

from rayforge.core.hooks import hookimpl

from .core.fonts import load_installed_fonts

ADDON_NAME = "sketcher"


@hookimpl
def rayforge_init(context):
    """Load user-installed fonts so job geometry uses the same faces."""
    load_installed_fonts()


@hookimpl
def register_asset_types(asset_type_registry):
    """Register Sketch asset type with the asset type registry."""
    load_installed_fonts()
    from .core.sketch import Sketch

    asset_type_registry.register(Sketch, "sketch", ADDON_NAME)


@hookimpl
def register_renderers(renderer_registry):
    """Register sketch renderer with the renderer registry."""
    from .image.renderer import SKETCH_RENDERER

    renderer_registry.register(SKETCH_RENDERER, ADDON_NAME)


@hookimpl
def register_exporters(exporter_registry):
    """Register sketch exporter with the exporter registry."""
    from .image.exporter import SketchExporter

    exporter_registry.register(SketchExporter, ADDON_NAME)


@hookimpl
def register_importers(importer_registry):
    """Register sketch importer with the importer registry."""
    from .image.importer import SketchImporter

    importer_registry.register(SketchImporter)
