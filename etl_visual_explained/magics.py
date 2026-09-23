from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.display import display

from .core.executor import LineageExecutor
from .ui import render_graph

@magics_class
class VisualChainMagic(Magics):

    @cell_magic
    def visual_chain(self, line, cell):
        """
        Jupyter cell magic to trace and visualize pandas ETL lineage: method
        chains AND joins/merges between multiple tables defined in the same
        cell.
        Usage:
        %%visual_chain
        enriched = (
            orders
            .merge(customers, on="customer_id")
            .assign(...)
        )
        """
        executor = LineageExecutor(cell, self.shell.user_ns, self.shell.user_global_ns)
        graph = executor.execute()

        # Also run the cell normally so the variables are updated in the namespace
        self.shell.run_cell(cell)

        # Keep a strong reference so node.ref (the real DataFrames) stays
        # alive for later clicks, even after this cell finishes running.
        self.shell.user_ns['_etl_last_graph'] = graph

        display(render_graph(graph))
