from IPython.display import HTML
import html
from ..core.models import ChainResult

class HTMLRenderer:
    """Renders the ChainResult into a beautiful HTML visualization for Jupyter."""
    
    def __init__(self, result: ChainResult):
        self.result = result
        
    def _generate_css(self) -> str:
        return """
        <style>
            .etl-visual-container {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 16px;
                margin-top: 10px;
                border: 1px solid #e9ecef;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }
            .etl-visual-header {
                font-size: 1.2em;
                font-weight: bold;
                color: #212529;
                margin-bottom: 12px;
                border-bottom: 2px solid #007bff;
                padding-bottom: 8px;
            }
            .etl-step-card {
                background: white;
                border-left: 4px solid #007bff;
                border-radius: 4px;
                padding: 12px;
                margin-bottom: 12px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .etl-step-card.error {
                border-left-color: #dc3545;
            }
            .etl-step-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            .etl-step-title {
                font-weight: bold;
                color: #007bff;
                font-size: 1.1em;
            }
            .etl-step-time {
                font-size: 0.85em;
                color: #6c757d;
                background: #e9ecef;
                padding: 2px 6px;
                border-radius: 10px;
            }
            .etl-code-snippet {
                background: #272822;
                color: #f8f8f2;
                padding: 8px;
                border-radius: 4px;
                font-family: 'Courier New', Courier, monospace;
                font-size: 0.9em;
                margin-bottom: 10px;
                overflow-x: auto;
            }
            .etl-metrics {
                display: flex;
                gap: 16px;
                font-size: 0.9em;
            }
            .etl-metric-box {
                background: #e3f2fd;
                border: 1px solid #bbdefb;
                padding: 6px 10px;
                border-radius: 4px;
                color: #0d47a1;
            }
            .etl-diff-positive { color: #28a745; font-weight: bold; }
            .etl-diff-negative { color: #dc3545; font-weight: bold; }
            .etl-diff-neutral { color: #6c757d; }
            
            .etl-preview-toggle {
                cursor: pointer;
                color: #007bff;
                text-decoration: underline;
                font-size: 0.9em;
                margin-top: 8px;
                display: inline-block;
            }
            .etl-preview-content {
                display: none;
                margin-top: 8px;
                font-size: 0.85em;
                overflow-x: auto;
            }
        </style>
        """
        
    def _render_shape_diff(self, step) -> str:
        if not step.state_before or not step.state_after:
            return ""
            
        rows_before, cols_before = step.state_before.shape
        rows_after, cols_after = step.state_after.shape
        
        row_diff = rows_after - rows_before
        col_diff = cols_after - cols_before
        
        def format_diff(diff: int) -> str:
            if diff > 0: return f"<span class='etl-diff-positive'>+{diff}</span>"
            if diff < 0: return f"<span class='etl-diff-negative'>{diff}</span>"
            return f"<span class='etl-diff-neutral'>0</span>"
            
        return f"""
        <div class="etl-metric-box">
            <strong>Rows:</strong> {rows_after} ({format_diff(row_diff)})
        </div>
        <div class="etl-metric-box">
            <strong>Cols:</strong> {cols_after} ({format_diff(col_diff)})
        </div>
        """

    def render(self) -> HTML:
        html_out = [self._generate_css()]
        html_out.append("<div class='etl-visual-container'>")
        html_out.append(f"<div class='etl-visual-header'>🛠️ ETL Visual Chain (Total: {self.result.total_time_ms:.2f}ms)</div>")
        
        if self.result.error:
             html_out.append(f"<div class='etl-step-card error'>❌ Error: {html.escape(self.result.error)}</div>")
        
        for step in self.result.steps:
            # Generate unique ID for toggle JS
            step_id = f"step_{step.step_index}"
            
            card_html = f"""
            <div class="etl-step-card">
                <div class="etl-step-header">
                    <span class="etl-step-title">Step {step.step_index}: <code>{step.operation_name}</code></span>
                    <span class="etl-step-time">⏱️ {step.execution_time_ms:.2f} ms</span>
                </div>
                <div class="etl-code-snippet">{html.escape(step.code_snippet)}</div>
                <div class="etl-metrics">
                    {self._render_shape_diff(step)}
                </div>
            """
            
            if step.state_after and step.state_after.head_preview:
                card_html += f"""
                <div class="etl-preview-toggle" onclick="document.getElementById('preview_{step_id}').style.display = document.getElementById('preview_{step_id}').style.display === 'none' ? 'block' : 'none'">
                    👀 Toggle Data Preview
                </div>
                <div id="preview_{step_id}" class="etl-preview-content">
                    {step.state_after.head_preview}
                </div>
                """
                
            card_html += "</div>"
            html_out.append(card_html)
            
        html_out.append("</div>")
        
        # We wrap in HTML object for Jupyter
        return HTML("\n".join(html_out))
