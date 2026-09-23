"""UI Module for ET Visual Explained"""

from ..core.models import LineageGraph
from .renderer import StaticGraphRenderer


def render_graph(graph: LineageGraph, prefer_widget: bool = True):
    """Render a LineageGraph, preferring the interactive anywidget-based
    widget (lazy row_count/preview on click) and falling back to a
    self-contained static render when anywidget isn't available in the
    current context (plain scripts, headless tests, notebook export)."""
    if prefer_widget:
        try:
            from .widget import LineageWidget
            return LineageWidget(graph)
        except ImportError:
            pass
    return StaticGraphRenderer(graph).render_static(eager_details=True)
