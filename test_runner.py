from IPython.terminal.interactiveshell import TerminalInteractiveShell
from etl_visual_explained.magics import VisualChainMagic

# Initialize shell
shell = TerminalInteractiveShell.instance()

# Register the magic
magic = VisualChainMagic(shell)
shell.register_magics(magic)

# Setup initial scope
shell.run_cell('''
import pandas as pd
import numpy as np
df = pd.read_csv("test_data.csv")
categories = pd.read_csv("categories.csv")
''')

from etl_visual_explained.core.executor import LineageExecutor
from etl_visual_explained.ui.renderer import StaticGraphRenderer

print("Testing visual_chain magic (single-table chain)...")

single_table_cell = """
result_df = (
    df
    .dropna()
    .filter(items=["id", "category", "value"])
    .assign(new_value=lambda x: x["value"] * 2)
    .groupby("category")
    .mean()
)
"""

# Call the magic method directly for testing outside a notebook environment
# The first argument 'line' is empty string for cell magic
magic.visual_chain("", single_table_cell)

graph = LineageExecutor(single_table_cell, shell.user_ns, shell.user_ns).execute()
html_obj = StaticGraphRenderer(graph).render_static(eager_details=True)
html_str = html_obj.data if hasattr(html_obj, "data") else str(html_obj)

assert "etl-graph-root" in html_str, "graph root container not found"
assert 'role="tablist"' in html_str, "tablist ARIA role missing"
assert 'role="tab"' in html_str, "tab ARIA role missing"
assert 'role="tabpanel"' in html_str, "tabpanel ARIA role missing"
assert "dropna" in html_str, "expected step 'dropna' in graph"
assert "filter" in html_str, "expected step 'filter' in graph"
assert "assign" in html_str, "expected step 'assign' in graph"
assert "groupby" in html_str, "expected step 'groupby' in graph"
print(f"Test passed: structural assertions OK ({len(html_str):,} bytes).")

print("\nTesting multi-table lineage (merge) in a single cell...")

join_cell = """
enriched = (
    df
    .dropna()
    .merge(categories, on="category", how="left")
    .assign(is_big=lambda x: x["value"] > 50)
)
"""

join_graph = LineageExecutor(join_cell, shell.user_ns, shell.user_ns).execute()

merge_nodes = [n for n in join_graph.nodes.values() if n.operation_name == "merge"]
assert len(merge_nodes) == 1, "expected exactly one merge node"
assert len(merge_nodes[0].parent_ids) == 2, "merge node must have 2 parents (join)"

base_vars = {n.origin_var for n in join_graph.roots()}
assert {"df", "categories"} <= base_vars, "both base tables must appear as roots"

join_html_obj = StaticGraphRenderer(join_graph).render_static(eager_details=True)
join_html_str = join_html_obj.data if hasattr(join_html_obj, "data") else str(join_html_obj)
assert "merge" in join_html_str
assert "etl-graph-edge" in join_html_str, "expected SVG edges connecting parents to children"
print(f"Test passed: merge node has 2 parents, both base tables tracked ({len(join_html_str):,} bytes).")

print("\nAll tests finished.")
