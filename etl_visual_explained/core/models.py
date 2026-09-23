from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TableMetadata:
    """Cheap, always-available metadata about a table (columns/dtypes)."""
    columns: List[str]
    dtypes: Dict[str, str]


@dataclass
class LineageNode:
    """A single node in the ETL lineage graph.

    `parent_ids` has 0 entries for a base table external to the cell, 1 entry
    for a normal transformation step, and 2+ entries for a join/merge.
    `row_count` and `preview_html` stay None until explicitly requested by the
    UI layer (lazy: computing them can be expensive on large/distributed
    tables), while `metadata` is computed eagerly since it's cheap.
    """
    node_id: str
    label: str
    code_snippet: str
    operation_name: Optional[str] = None
    parent_ids: List[str] = field(default_factory=list)
    origin_var: Optional[str] = None
    is_base: bool = False
    is_error: bool = False
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    adapter_name: Optional[str] = None
    metadata: Optional[TableMetadata] = None
    row_count: Optional[int] = None
    preview_html: Optional[str] = None
    ref: Any = field(default=None, repr=False, compare=False)


@dataclass
class LineageGraph:
    """The full lineage graph produced from one cell."""
    original_code: str
    nodes: Dict[str, LineageNode] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)
    statement_outputs: List[str] = field(default_factory=list)
    total_time_ms: float = 0.0
    error: Optional[str] = None

    def add_node(self, node: LineageNode) -> None:
        self.nodes[node.node_id] = node
        self.order.append(node.node_id)

    def get(self, node_id: str) -> LineageNode:
        return self.nodes[node_id]

    def roots(self) -> List[LineageNode]:
        return [n for n in self.nodes.values() if n.is_base]
