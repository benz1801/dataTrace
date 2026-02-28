from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time

@dataclass
class DataFrameState:
    """Represents the state of a DataFrame at a specific step."""
    shape: tuple[int, int]
    columns: List[str]
    dtypes: Dict[str, str]
    head_preview: str # HTML or text representation of the first few rows
    
@dataclass
class StepResult:
    """The result of executing a single step in the method chain."""
    step_index: int
    operation_name: str # e.g., "filter", "assign", "groupby"
    code_snippet: str
    execution_time_ms: float
    state_before: Optional[DataFrameState] = None
    state_after: Optional[DataFrameState] = None
    error: Optional[str] = None
    
@dataclass
class ChainResult:
    """The overall result of executing a method chain."""
    original_code: str
    steps: List[StepResult] = field(default_factory=list)
    total_time_ms: float = 0.0
    final_result: Any = None
    error: Optional[str] = None
