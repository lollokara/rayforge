import copy
import logging
import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from raygeo.geo import Geometry, Matrix
from raygeo.geo.shape.line import does_line_segment_intersect_rect
from raygeo.geo.shape.polygon import (
    get_polygons_group_difference,
    is_point_inside_polygon,
)
from raygeo.geo.shape.text import FontConfig, text_to_geometry
from raygeo.geo.types import Rect

from rayforge.core.color import ColorRGBA

from ..text_on_path import text_on_path
from ..types import EntityID
from .arc import Arc
from .bezier import Bezier
from .circle import Circle
from .entity import Entity
from .line import Line
from .polygon import rings_to_geometry

if TYPE_CHECKING:
    from ..constraints import Constraint
    from ..entity_group import PlacementTransform
    from ..registry import EntityRegistry

logger = logging.getLogger(__name__)

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

_PATH_ENTITY_TYPES = (Line, Arc, Circle, Bezier)
_PATH_TOLERANCE = 0.02
_CIRCLE_SEGMENTS = 96


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


class TextBoxEntity(Entity):
    def __init__(
        self,
        id: EntityID,
        origin_id: EntityID,
        width_id: EntityID,
        height_id: EntityID,
        content: str = "",
        font_config: FontConfig | None = None,
        construction: bool = False,
        construction_line_ids: list[EntityID] | None = None,
    ):
        super().__init__(id, construction)
        self.origin_id: EntityID = origin_id
        self.width_id: EntityID = width_id
        self.height_id: EntityID = height_id
        self.content = content
        self.font_config = font_config or FontConfig()
        self.construction_line_ids: list[EntityID] = (
            construction_line_ids or []
        )
        self.fill_color: ColorRGBA | None = None
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
        self.type = "text_box"

    def get_point_ids(self) -> list[EntityID]:
        return [self.origin_id, self.width_id, self.height_id]

    def get_endpoint_ids(self) -> list[EntityID]:
        return []

    def get_junction_point_ids(self) -> list[EntityID]:
        return []

    def get_helper_ids(self) -> list[EntityID]:
        return list(self.construction_line_ids)

    def clear_helper_references(self) -> None:
        self.construction_line_ids = []

    def supports_fill(self) -> bool:
        return True

    def set_fill_color(self, color: ColorRGBA | None) -> None:
        self.fill_color = color

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

    def get_frame_polygon(
        self, registry: "EntityRegistry"
    ) -> list[tuple[float, float]] | None:
        """Returns the 4-corner frame polygon, or None if points are
        missing.  Corner 4 is taken from the construction line when
        present, otherwise computed from the parallelogram identity."""
        p_origin = registry.get_point(self.origin_id)
        p_width = registry.get_point(self.width_id)
        p_height = registry.get_point(self.height_id)
        if not (p_origin and p_width and p_height):
            return None

        p4_id = self.get_fourth_corner_id(registry)
        if p4_id is not None:
            p4 = registry.get_point(p4_id)
            if p4:
                p4_x, p4_y = p4.x, p4.y
            else:
                p4_x = p_width.x + p_height.x - p_origin.x
                p4_y = p_width.y + p_height.y - p_origin.y
        else:
            p4_x = p_width.x + p_height.x - p_origin.x
            p4_y = p_width.y + p_height.y - p_origin.y

        return [
            (p_origin.x, p_origin.y),
            (p_width.x, p_width.y),
            (p4_x, p4_y),
            (p_height.x, p_height.y),
        ]

    def hit_test(
        self,
        mx: float,
        my: float,
        threshold: float,
        registry: "EntityRegistry",
    ) -> bool:
        polygon = self.get_frame_polygon(registry)
        if polygon is None:
            return False
        return is_point_inside_polygon((mx, my), polygon)

    def get_all_frame_point_ids(
        self, registry: "EntityRegistry"
    ) -> list[EntityID]:
        """Returns all 4 corner points of the text box frame."""
        ids = [self.origin_id, self.width_id, self.height_id]
        p4_id = self.get_fourth_corner_id(registry)
        if p4_id is not None:
            ids.append(p4_id)
        return ids

    def get_font_metrics(self) -> tuple[float, float, float]:
        return self.font_config.get_font_metrics()

    def get_natural_size(
        self, content: str | None = None
    ) -> tuple[float, float]:
        """
        Returns the natural (width, height) of the text content.

        If *content* is omitted, uses ``self.content``. An empty or
        None content yields a minimum width of 10.

        The height is derived from the actual geometry bounding box
        so the frame matches the ink extent exactly and map_to_frame
        does not stretch the text.  raygeo returns Y-UP geometry.`
        """
        text = content if content is not None else self.content

        if not text:
            return 10.0, self.font_config.size

        _, width, _, height = self._natural_layout(text)
        return max(width, 1.0), max(height, 1.0)

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
            geo.transform(Matrix.scale(-1.0, 1.0, center=(width / 2.0, 0.0)))
        return geo, width, min_y, height

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

    def _frame_glyphs(self, registry: "EntityRegistry", text: str) -> Geometry:
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
        path_entity = (
            registry.get_entity(self.path_entity_id)
            if self.path_entity_id is not None
            else None
        )
        if self.content_bottom and isinstance(path_entity, Circle):
            geo.extend(
                text_on_path(
                    self.content_bottom,
                    self.font_config,
                    polyline,
                    "inside",
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

    def get_plate_ring(
        self, registry: "EntityRegistry"
    ) -> list[tuple[float, float]] | None:
        """The knock-out plate: the frame grown by the margin and
        rotated with the text. None when knock-out is off."""
        if not self.knockout or self.get_path_polyline(registry) is not None:
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
        glyphs = self._glyphs(registry, text)
        ring = self.get_plate_ring(registry)
        if ring is None:
            return glyphs
        return rings_to_geometry(
            get_polygons_group_difference([ring], glyphs.to_polygons(0.02))
        )

    def get_fourth_corner_id(
        self, registry: "EntityRegistry"
    ) -> EntityID | None:
        """Finds the 4th point ID of the text box."""
        for eid in self.construction_line_ids:
            entity = registry.get_entity(eid)
            if isinstance(entity, Line):
                if entity.p1_idx == self.width_id and (
                    entity.p2_idx != self.origin_id
                    and entity.p2_idx != self.height_id
                ):
                    return entity.p2_idx
                if entity.p2_idx == self.width_id and (
                    entity.p1_idx != self.origin_id
                    and entity.p1_idx != self.height_id
                ):
                    return entity.p1_idx
        return None

    def get_state(self) -> dict[str, Any]:
        state = super().get_state()
        if state is not None:
            state["fill_color"] = self.fill_color
        else:
            state = {"fill_color": self.fill_color}
        return state

    def set_state(self, state: dict[str, Any]) -> None:
        super().set_state(state)
        if "fill_color" in state:
            self.fill_color = state["fill_color"]

    def update_constrained_status(
        self, registry: "EntityRegistry", constraints: Sequence["Constraint"]
    ) -> None:
        p_origin = registry.get_point(self.origin_id)
        p_width = registry.get_point(self.width_id)
        p_height = registry.get_point(self.height_id)
        self.constrained = (
            p_origin.constrained
            and p_width.constrained
            and p_height.constrained
        )

    def geometry_signature(self, registry: "EntityRegistry") -> tuple:
        """Extends the point signature with the content and font,
        which shape the rendered glyphs without moving the frame."""
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

    def rewrite_offsets_from(
        self, template: "Entity", placement: "PlacementTransform"
    ) -> None:
        """Re-derives the copy's content, font and fill from the
        template so template edits propagate to every member."""
        if not isinstance(template, TextBoxEntity):
            return
        self.content = template.content
        self.font_config = copy.deepcopy(template.font_config)
        self.fill_color = template.fill_color
        self.set_style(template.get_style())

    def to_polylines(
        self,
        registry: "EntityRegistry",
        tolerance: float = 0.1,
    ) -> list[list[tuple[float, float]]]:
        """Samples every glyph contour into its own polyline, so
        previews show the full text instead of a single contour."""
        return self.to_geometry(registry).to_polygons(tolerance)

    def is_contained_by(
        self,
        rect: Rect,
        registry: "EntityRegistry",
    ) -> bool:
        points = self.get_frame_polygon(registry)
        if points is None:
            return False

        return all(
            rect[0] <= px <= rect[2] and rect[1] <= py <= rect[3]
            for px, py in points
        )

    def intersects_rect(
        self,
        rect: Rect,
        registry: "EntityRegistry",
    ) -> bool:
        points = self.get_frame_polygon(registry)
        if points is None:
            return False

        for i in range(4):
            p1 = points[i]
            p2 = points[(i + 1) % 4]
            if does_line_segment_intersect_rect(p1, p2, rect):
                return True

        return any(
            rect[0] <= px <= rect[2] and rect[1] <= py <= rect[3]
            for px, py in points
        )

    def _build_frame_for_content(
        self,
        registry: "EntityRegistry",
        content: str,
    ) -> tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ]:
        """
        Builds a frame (origin, p_width, p_height) whose dimensions match
        *content*'s natural size, preserving direction vectors from the
        current frame.

        Returns (origin, p_width, p_height).
        """
        p_origin = registry.get_point(self.origin_id)
        p_width = registry.get_point(self.width_id)
        p_height = registry.get_point(self.height_id)

        if content == self.content or not self.content:
            logger.debug(
                f"_build_frame: no scaling, content == self.content "
                f"({content!r} == {self.content!r}) or empty"
            )
            return (
                (p_origin.x, p_origin.y),
                (p_width.x, p_width.y),
                (p_height.x, p_height.y),
            )

        nat_w, nat_h = self.get_natural_size(content)

        dx = p_width.x - p_origin.x
        dy = p_width.y - p_origin.y
        frame_w = math.hypot(dx, dy)

        if frame_w < 1e-9:
            w_scale = 1.0
        else:
            w_scale = nat_w / frame_w

        logger.debug(
            f"_build_frame: scaling content={content!r} "
            f"nat_w={nat_w:.2f} frame_w={frame_w:.2f} "
            f"w_scale={w_scale:.4f}"
        )

        scaled_width = (
            p_origin.x + dx * w_scale,
            p_origin.y + dy * w_scale,
        )

        hx = p_height.x - p_origin.x
        hy = p_height.y - p_origin.y
        frame_h = math.hypot(hx, hy)

        if frame_h < 1e-9:
            h_scale = 1.0
        else:
            h_scale = nat_h / frame_h

        scaled_height = (
            p_origin.x + hx * h_scale,
            p_origin.y + hy * h_scale,
        )

        return (
            (p_origin.x, p_origin.y),
            scaled_width,
            scaled_height,
        )

    def to_geometry(
        self,
        registry: "EntityRegistry",
        resolved_content: str | None = None,
    ) -> Geometry:
        """Converts the text box to a Geometry object."""
        text = (
            resolved_content if resolved_content is not None else self.content
        )
        glyphs = self._glyphs(registry, text)
        ring = self.get_plate_ring(registry)
        if ring is None:
            return glyphs
        plate = rings_to_geometry([ring])
        plate.extend(glyphs)
        return plate

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "origin_id": self.origin_id,
                "width_id": self.width_id,
                "height_id": self.height_id,
                "content": self.content,
                "font_config": self.font_config.to_dict(),
                "construction_line_ids": self.construction_line_ids,
            }
        )
        if self.fill_color is not None:
            data["fill_color"] = list(self.fill_color)
        for key, default in STYLE_DEFAULTS.items():
            value = getattr(self, key)
            if value != default:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextBoxEntity":
        fill_color_raw = data.get("fill_color")
        fill_color = (
            tuple(fill_color_raw) if fill_color_raw is not None else None
        )
        entity = cls(
            id=data["id"],
            origin_id=data["origin_id"],
            width_id=data["width_id"],
            height_id=data["height_id"],
            content=data.get("content", ""),
            font_config=FontConfig.from_dict(data.get("font_config")),
            construction=data.get("construction", False),
            construction_line_ids=data.get("construction_line_ids"),
        )
        entity.fill_color = fill_color
        entity.set_style(data)
        return entity

    def __repr__(self) -> str:
        return (
            f"TextBoxEntity(id={self.id}, origin={self.origin_id}, "
            f"width={self.width_id}, height={self.height_id}, "
            f"content='{self.content}')"
        )
