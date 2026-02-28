A tool for visual explanation of ETL pipelines of structured data

**etl_visual_explained** is a Jupyter tool for visual debugging and step-by-step analysis of Pandas (and potentially Polars) data pipelines, designed to make every transformation in ETL processes transparent.

## Main Features
- **Magic command** `%%visual_chain` for Jupyter notebooks: executes and visualizes each step of a Pandas method chain, showing the DataFrame state after every transformation.
- **Interactive HTML visualization**: each step is displayed with details about code, execution time, data preview, and metadata (shape, columns, dtypes).
- **Detailed analysis**: errors and performance are tracked step-by-step, making pipeline debugging and optimization easier.
- **Extensible**: the modular structure (parser, executor, renderer) allows easy adaptation to new use cases or libraries.

## Project Structure
- `etl_visual_explained/magics.py`: defines the `%%visual_chain` cell magic for Jupyter.
- `etl_visual_explained/core/`: contains the parsing logic (`parser.py`), step-by-step execution (`executor.py`), and data models (`models.py`).
- `etl_visual_explained/ui/renderer.py`: generates the HTML visualization of pipeline steps.
- `try.ipynb`: example notebook with data generation and magic usage.

## Usage Example
```python
%load_ext etl_visual_explained

# In a Jupyter cell:
%%visual_chain
df = (
	my_df
	.filter(...)
	.assign(...)
	# other transformations
)
```

## Requirements
- Python >= 3.9
- pandas >= 1.5.0
- ipython >= 8.0.0
- anywidget >= 0.9.0 (optional)
- traitlets >= 5.0.0

For details and customization, see the source code and the example notebook.

