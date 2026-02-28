from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.display import display

from .core.executor import ChainExecutor
from .ui.renderer import HTMLRenderer

@magics_class
class VisualChainMagic(Magics):
    
    @cell_magic
    def visual_chain(self, line, cell):
        """
        Jupyter cell magic to trace and visualize pandas method chains.
        Usage:
        %%visual_chain
        df = (
            my_df
            .filter(...)
            .assign(...)
        )
        """
        # Execute chain
        executor = ChainExecutor(cell, self.shell.user_ns, self.shell.user_global_ns)
        result = executor.execute()
        
        # Also run the cell normally so the variables are updated in the namespace
        self.shell.run_cell(cell)
        
        # Render the UI
        renderer = HTMLRenderer(result)
        display(renderer.render())
