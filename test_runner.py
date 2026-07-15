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
''')

print("Testing visual_chain magic...")

# Run the magic
cell_code = """
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
magic.visual_chain("", cell_code)

# Render the pipeline independently so we can inspect the HTML (the magic
# itself uses IPython.display, which doesn't return the object).
from etl_visual_explained.core.executor import ChainExecutor
from etl_visual_explained.ui.renderer import HTMLRenderer

executor = ChainExecutor(cell_code, shell.user_ns, shell.user_ns)
result = executor.execute()
html_obj = HTMLRenderer(result).render()
html_str = html_obj.data if hasattr(html_obj, "data") else str(html_obj)

# Basic structural assertions on the rendered HTML.
assert "etl-pipe-root" in html_str, "pipeline root container not found"
assert "etl-pipe-timeline" in html_str, "timeline not found"
assert 'role="tablist"' in html_str, "tablist ARIA role missing"
assert 'role="tab"' in html_str, "tab ARIA role missing"
assert 'role="tabpanel"' in html_str, "tabpanel ARIA role missing"
assert "dropna" in html_str, "expected step 'dropna' in timeline"
assert "filter" in html_str, "expected step 'filter' in timeline"
assert "assign" in html_str, "expected step 'assign' in timeline"
assert "groupby" in html_str, "expected step 'groupby' in timeline"
assert "▶" in html_str, "connector arrows missing"
# Diff-in-the-connector (signature): at least one delta annotation
assert any(d in html_str for d in ["rows", "cols"]), "no shape diff in any connector"
print("Test passed: structural assertions OK.")
print(f"HTML size: {len(html_str):,} bytes")

print("Test finished.")
