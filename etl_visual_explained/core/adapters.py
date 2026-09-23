from typing import Any, List, Optional, Protocol, runtime_checkable

from .models import TableMetadata, LineageNode


@runtime_checkable
class TableAdapter(Protocol):
    """Backend-specific access to a table-like object.

    `get_cheap_metadata` must never trigger a computation (columns/dtypes are
    metadata, not data). `get_row_count`/`get_preview_html` are allowed to be
    expensive (e.g. a distributed job on Spark) and are only ever called
    on demand, never eagerly by the executor.
    """
    name: str

    def matches(self, obj: Any) -> bool: ...
    def get_cheap_metadata(self, obj: Any) -> TableMetadata: ...
    def get_row_count(self, obj: Any) -> int: ...
    def get_preview_html(self, obj: Any, n: int = 5) -> str: ...


class PandasAdapter:
    name = "pandas"

    def matches(self, obj: Any) -> bool:
        import pandas as pd
        return isinstance(obj, pd.DataFrame)

    def get_cheap_metadata(self, obj: Any) -> TableMetadata:
        return TableMetadata(
            columns=[str(c) for c in obj.columns],
            dtypes={str(c): str(t) for c, t in obj.dtypes.items()},
        )

    def get_row_count(self, obj: Any) -> int:
        return int(obj.shape[0])

    def get_preview_html(self, obj: Any, n: int = 5) -> str:
        return obj.head(n).to_html(classes="table table-sm", index=False)


class AdapterRegistry:
    """Extensible registry of table adapters, checked in registration order."""

    def __init__(self) -> None:
        self._adapters: List[TableAdapter] = []

    def register(self, adapter: TableAdapter) -> None:
        self._adapters.append(adapter)

    def find(self, obj: Any) -> Optional[TableAdapter]:
        for adapter in self._adapters:
            try:
                if adapter.matches(obj):
                    return adapter
            except Exception:
                continue
        return None


default_registry = AdapterRegistry()
default_registry.register(PandasAdapter())

# Next iteration: a SparkAdapter for pyspark.sql.DataFrame, registered only if
# pyspark is importable, so it never becomes a hard dependency of this package.
# try:
#     from .spark_adapter import SparkAdapter
#     default_registry.register(SparkAdapter())
# except ImportError:
#     pass


def compute_row_count(node: LineageNode) -> Optional[int]:
    """Materialize `node.row_count` on demand. Cached after the first call."""
    if node.row_count is not None or node.ref is None:
        return node.row_count
    adapter = default_registry.find(node.ref)
    if adapter is None:
        return None
    node.row_count = adapter.get_row_count(node.ref)
    return node.row_count


def compute_preview_html(node: LineageNode, n: int = 5) -> Optional[str]:
    """Materialize `node.preview_html` on demand. Cached after the first call."""
    if node.preview_html is not None or node.ref is None:
        return node.preview_html
    adapter = default_registry.find(node.ref)
    if adapter is None:
        return None
    node.preview_html = adapter.get_preview_html(node.ref, n)
    return node.preview_html
