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

print("Test finished.")
