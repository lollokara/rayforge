import logging
import re
from typing import Any

from .evaluator import MATH_CONTEXT

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")


class ExpressionMap:
    """
    Evaluates ``{expression}`` placeholders in template strings using
    a sandboxed eval namespace.

    Uses the same ``MATH_CONTEXT`` as ``safe_evaluate()``, but returns
    whatever type the expression produces (no float coercion).

    Supports Python format specs: ``{value:04d}``, ``{width:.1f}``, etc.

    Unlike ``str.format_map()``, this uses regex-based substitution
    so expressions can contain attribute access
    (e.g. ``{date.today()}``).

    Usage::

        values = {"width": 50.0, "height": 30.0}
        tpl = "Part {width:.1f}x{height:.1f}"
        resolved = ExpressionMap(values).format(tpl)
        # "Part 50.0x30.0"
    """

    def __init__(self, values: dict[str, Any] | None = None):
        self._namespace: dict[str, Any] = MATH_CONTEXT.copy()
        if values:
            self._namespace.update(values)
        self._namespace["__builtins__"] = {}

    def _evaluate(self, match: re.Match) -> tuple[str, bool]:
        key = match.group(1)
        expr, _, fmt = key.partition(":")
        try:
            result = eval(expr.strip(), self._namespace)
        except Exception as e:  # noqa: BLE001 - arbitrary user expression
            logger.debug(f"Failed to evaluate expression '{expr}': {e}")
            return match.group(0), False
        if fmt:
            try:
                return format(result, fmt), True
            except (ValueError, TypeError):
                return str(result), True
        return str(result), True

    def segments(self, template: str) -> list[tuple[str, bool]]:
        """
        Splits the resolved *template* into ``(text, is_dynamic)``
        pieces. Text produced by a successfully evaluated placeholder
        is dynamic; literal text and unresolvable placeholders are not.
        """
        result: list[tuple[str, bool]] = []
        pos = 0
        for match in _PLACEHOLDER_RE.finditer(template):
            if match.start() > pos:
                result.append((template[pos : match.start()], False))
            result.append(self._evaluate(match))
            pos = match.end()
        if pos < len(template):
            result.append((template[pos:], False))
        return result

    def format(self, template: str) -> str:
        """Resolve all ``{expression}`` placeholders in *template*."""
        return "".join(text for text, _ in self.segments(template))
