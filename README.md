A tool for visual explanation of ETL pipelines of structured data

**etl_visual_explained** is a Jupyter tool for visual debugging and step-by-step analysis of Pandas data pipelines, designed to make every transformation in ETL processes transparent — including joins/merges between multiple tables.

## Main Features
- **Magic command** `%%visual_chain` for Jupyter notebooks: executes and visualizes an ETL cell as a **lineage graph**, not just a linear chain — a `.merge()`/`.join()` between two tables shows up as a node with two parents.
- **Interactive graph**: each node shows code, execution time, columns/dtypes; row count and data preview are computed **on demand** (click "Calcola righe e anteprima"), not eagerly for every node — important for large tables and for the planned Spark backend, where counting rows or previewing data triggers a distributed job.
- **Extensible backend**: table introspection (columns/dtypes/row-count/preview) goes through a `TableAdapter` layer (`core/adapters.py`); only a `PandasAdapter` exists today, a `SparkAdapter` is the next step.

## Project Structure
- `etl_visual_explained/magics.py`: defines the `%%visual_chain` cell magic for Jupyter.
- `etl_visual_explained/core/`: parsing into a lineage graph plan (`parser.py`), single-pass execution (`executor.py`), backend adapters (`adapters.py`), and the graph data model (`models.py`).
- `etl_visual_explained/ui/`: DAG layout (`graph_layout.py`), the graph renderer (`renderer.py`), and the interactive `anywidget`-based widget (`widget.py`) used for on-demand row-count/preview.
- `try.ipynb`: example notebook with data generation and magic usage.

## Usage Example
```python
%load_ext etl_visual_explained

# In a Jupyter cell — multiple tables in the same cell are tracked together:
%%visual_chain
enriched = (
    orders
    .merge(customers, on="customer_id")
    .assign(...)
)
```

## Roadmap and known limitations
- **Scope**: lineage tracking only spans statements inside the **same cell** — a table produced in one cell and joined in a later cell is treated as an untracked external base table, not linked to its own history.
- **Join style**: only method-style joins are recognized (`a.merge(b, ...)`, `a.join(b)`); a functional style like `pd.merge(a, b)` or `pd.concat([a, b])` used as the very first node of a chain is not parsed for its real parents (it still runs, but the lineage graph won't be fully accurate for that node).
- **Assignment targets**: only simple `x = ...` assignments update the lineage; tuple-unpacking (`a, b = ...`) or attribute/subscript targets are not tracked as reusable variables for later statements.
- **Spark/Databricks**: the primary target backend going forward (most collaborators work in Databricks). The adapter layer already separates "cheap" metadata (columns/schema — free even for Spark) from "expensive" data (row count/preview — a Spark action), so a future `SparkAdapter` can plug in without touching the parser/executor/UI.

## Requirements
- Python >= 3.9
- pandas >= 1.5.0
- ipython >= 8.0.0
- anywidget >= 0.9.0 (used for the interactive lineage graph; falls back to a static render if unavailable)
- traitlets >= 5.0.0

For details and customization, see the source code and the example notebook.

