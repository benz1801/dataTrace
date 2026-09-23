from typing import Dict, Tuple

from ..core.models import LineageGraph


def compute_layout(graph: LineageGraph) -> Dict[str, Tuple[int, int]]:
    """Simple layered DAG layout, no external graphing dependency.

    column = longest-path depth from any root (0 for base nodes).
    row = position among nodes sharing the same column, in creation order.
    """
    depth: Dict[str, int] = {}
    for node_id in graph.order:
        node = graph.get(node_id)
        if not node.parent_ids:
            depth[node_id] = 0
        else:
            depth[node_id] = max(depth[p] for p in node.parent_ids) + 1

    row_counts: Dict[int, int] = {}
    positions: Dict[str, Tuple[int, int]] = {}
    for node_id in graph.order:
        col = depth[node_id]
        row = row_counts.get(col, 0)
        row_counts[col] = row + 1
        positions[node_id] = (col, row)
    return positions
