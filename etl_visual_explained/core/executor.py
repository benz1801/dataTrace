import ast
import time
import pandas as pd
from typing import Dict, Any

from .models import StepResult, ChainResult, DataFrameState
from .parser import ChainParser

class ChainExecutor:
    """Executes a parsed method chain step-by-step."""
    
    def __init__(self, code: str, local_ns: Dict[str, Any], global_ns: Dict[str, Any]):
        self.code = code
        self.parser = ChainParser(code)
        self.local_ns = local_ns
        self.global_ns = global_ns
        
    def _extract_state(self, obj: Any) -> DataFrameState:
        """Extracts metadata from a pandas DataFrame."""
        if isinstance(obj, pd.DataFrame):
            return DataFrameState(
                shape=obj.shape,
                columns=list(obj.columns),
                dtypes={col: str(dtype) for col, dtype in obj.dtypes.items()},
                head_preview=obj.head(3).to_html(classes="table table-sm", index=False)
            )
        return None

    def execute(self) -> ChainResult:
        result = ChainResult(original_code=self.code)
        
        try:
            chain_nodes = self.parser.extract_chain_steps()
            if not chain_nodes:
                result.error = "No valid method chain found."
                return result
                
            # Base object Evaluation (e.g., 'df')
            base_node = chain_nodes[0]
            base_code = ast.unparse(base_node)
            current_obj = eval(base_code, self.global_ns, self.local_ns)
            
            # Step evaluation
            start_time_total = time.perf_counter()
            previous_state = self._extract_state(current_obj)
            
            for i in range(1, len(chain_nodes)):
                node = chain_nodes[i]
                
                # To evaluate a single step in a chain `obj.method(...)`,
                # we compile the node but substitute the base with our `current_obj`.
                # Alternatively, we evaluate the *full code up to this node*.
                
                # A safer MVP approach: reconstruct code up to the current node
                step_code = ast.unparse(node)
                
                start_step = time.perf_counter()
                
                # Execute the code up to this step
                # NOTE: This re-evaluates from the start. A more advanced executor
                # would patch the base object. For MVP, re-evaluating provides correct state
                # but might be slow for heavy pipelines. We'll optimize later.
                next_obj = eval(step_code, self.global_ns, self.local_ns)
                
                end_step = time.perf_counter()
                
                current_state = self._extract_state(next_obj)
                
                operation_name = "Unknown"
                if isinstance(node, ast.Call) and hasattr(node.func, "attr"):
                    operation_name = node.func.attr
                elif isinstance(node, ast.Attribute):
                    operation_name = node.attr
                    
                result.steps.append(StepResult(
                    step_index=i,
                    operation_name=operation_name,
                    code_snippet=step_code,
                    execution_time_ms=(end_step - start_step) * 1000,
                    state_before=previous_state,
                    state_after=current_state
                ))
                
                current_obj = next_obj
                previous_state = current_state

            result.final_result = current_obj
            result.total_time_ms = (time.perf_counter() - start_time_total) * 1000
            
        except Exception as e:
            result.error = f"Execution failed: {str(e)}"
            
        return result
