import ast

class ChainParser:
    """Parses Python code involving pandas/polars method chaining."""
    
    def __init__(self, code: str):
        self.code = code
        self.tree = ast.parse(code)
    
    def extract_chain_steps(self) -> list[ast.Call]:
        """
        Extracts the individual calls from a method chain.
        Returns a list of ast nodes representing each step, ordered from top to bottom.
        For example: `df.filter(...).assign(...)` will yield nodes for `df`, `filter`, and `assign`.
        """
        # We look for the first Expr or Assign statement in the code to keep it simple for MVP
        steps = []
        for node in self.tree.body:
            if isinstance(node, ast.Expr):
                # The expression might be a chained call
                current_node = node.value
            elif isinstance(node, ast.Assign):
                # The expression is assigned to a variable
                current_node = node.value
            else:
                continue
                
            # Unwind the chain from the outside in
            chain_nodes = []
            while isinstance(current_node, ast.Call) or isinstance(current_node, ast.Attribute):
                chain_nodes.append(current_node)
                if hasattr(current_node, "func"):
                    current_node = current_node.func.value
                elif hasattr(current_node, "value"):
                    current_node = current_node.value
                else:
                    break
            
            chain_nodes.append(current_node) # The base DataFrame (e.g. Name node "df")
            chain_nodes.reverse() # Order from left to right (base -> first call -> second call)
            
            if len(chain_nodes) > 1:
                steps = chain_nodes
                break # Found the main chain expression
                
        return steps
