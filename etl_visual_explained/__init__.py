"""ETL Visual Explained Package"""

__version__ = "0.1.0"

def load_ipython_extension(ipython):
    from .magics import VisualChainMagic
    ipython.register_magics(VisualChainMagic)
