import html
import json
from typing import Optional

from IPython.display import HTML

from ..core.adapters import compute_preview_html, compute_row_count
from ..core.models import LineageGraph, LineageNode
from .graph_layout import compute_layout

PFX = "etl-graph"

COL_W = 190
ROW_H = 100
NODE_W = 150
NODE_H = 70
PAD = 24


def _cols_str(node: LineageNode) -> str:
    if node.metadata is None:
        return "—"
    n_cols = len(node.metadata.columns)
    rows = node.row_count if node.row_count is not None else "?"
    return f"{rows}×{n_cols}"


class StaticGraphRenderer:
    """Renders a LineageGraph as a branching graph (nodes positioned by
    depth, SVG edges for parent -> child, including multi-parent joins).

    Two render modes:
    - `render_static(eager_details=True)`: computes row_count/preview for
      every node up front and embeds them in the page. Used as the fallback
      when no live Python<->JS channel exists (scripts, tests, static export).
    - `render_skeleton()`: returns bare markup with only cheap metadata
      (columns/dtypes); row_count/preview stay as "click to compute"
      placeholders, filled in later by `ui.widget.LineageWidget` over a
      real comm channel.
    """

    def __init__(self, graph: LineageGraph):
        self.graph = graph
        self.layout = compute_layout(graph)

    # ----- shared CSS -------------------------------------------------

    def _css(self) -> str:
        return f"""
        <style>
            .{PFX}-root {{
                font-family: 'Inter', 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
                background: #0F1115; color: #E6E8EC;
                border: 1px solid #262B36; border-radius: 8px;
                padding: 18px 20px 16px; margin: 10px 0;
                font-size: 13px; line-height: 1.45;
            }}
            .{PFX}-header {{
                display: flex; align-items: baseline; justify-content: space-between;
                gap: 12px; margin-bottom: 16px; padding-bottom: 10px;
                border-bottom: 1px solid #262B36;
            }}
            .{PFX}-title {{
                font-size: 14px; font-weight: 600; letter-spacing: 0.02em;
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
            }}
            .{PFX}-title .dot {{ color: #E8B339; margin-right: 6px; }}
            .{PFX}-meta {{
                font-family: 'JetBrains Mono', ui-monospace, monospace;
                font-size: 11px; color: #8A92A6; text-transform: uppercase; letter-spacing: 0.08em;
            }}
            .{PFX}-meta b {{ color: #E6E8EC; font-weight: 600; }}
            .{PFX}-err {{
                background: rgba(232, 74, 74, 0.08); border-left: 3px solid #E84A4A;
                color: #E84A4A; padding: 10px 14px; border-radius: 4px;
                font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;
                margin-bottom: 14px;
            }}
            .{PFX}-canvas {{ position: relative; overflow: auto; }}
            .{PFX}-canvas svg {{ position: absolute; top: 0; left: 0; pointer-events: none; }}
            .{PFX}-edge {{ stroke: #3a4150; stroke-width: 1.5; }}
            .{PFX}-edge.join {{ stroke: #E8B339; }}
            .{PFX}-node {{
                position: absolute; appearance: none; background: #181C24;
                border: 1px solid #262B36; border-radius: 6px; padding: 8px 10px;
                width: {NODE_W}px; height: {NODE_H}px; text-align: left; cursor: pointer;
                font: inherit; color: inherit; display: flex; flex-direction: column; gap: 3px;
                transition: border-color 120ms ease, background 120ms ease;
            }}
            .{PFX}-node:hover {{ border-color: #3a4150; background: #1c212b; }}
            .{PFX}-node:focus-visible {{ outline: none; border-color: #E8B339; box-shadow: 0 0 0 2px rgba(232, 179, 57, 0.25); }}
            .{PFX}-node[aria-selected="true"] {{ border-color: #E8B339; box-shadow: 0 0 0 1.5px #E8B339; background: #1c212b; }}
            .{PFX}-node.is-base {{ border-style: dashed; }}
            .{PFX}-node.is-error {{ border-color: #E84A4A; }}
            .{PFX}-node-name {{
                font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px;
                font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            }}
            .{PFX}-node.is-base .{PFX}-node-name {{ color: #E8B339; }}
            .{PFX}-node-shape {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; color: #8A92A6; }}
            .{PFX}-panel {{ display: none; background: #181C24; border: 1px solid #262B36; border-radius: 6px; padding: 14px 16px; margin-top: 12px; }}
            .{PFX}-panel.is-open {{ display: block; }}
            .{PFX}-panel-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
            @media (max-width: 720px) {{ .{PFX}-panel-grid {{ grid-template-columns: 1fr; }} }}
            .{PFX}-panel h4 {{ font-size: 11px; color: #8A92A6; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 8px; font-weight: 600; }}
            .{PFX}-code {{ background: #0B0D11; border: 1px solid #262B36; border-radius: 4px; padding: 10px 12px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12px; overflow-x: auto; white-space: pre; }}
            .{PFX}-metrics {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }}
            .{PFX}-chip {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; background: #0B0D11; border: 1px solid #262B36; border-radius: 4px; padding: 4px 8px; }}
            .{PFX}-chip b {{ color: #E8B339; font-weight: 600; }}
            .{PFX}-dtypes {{ font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; color: #8A92A6; margin-top: 8px; max-height: 120px; overflow-y: auto; }}
            .{PFX}-dtypes span {{ display: inline-block; margin-right: 12px; }}
            .{PFX}-dtypes b {{ color: #E6E8EC; }}
            .{PFX}-preview {{ margin-top: 12px; overflow-x: auto; font-family: 'Inter', system-ui, sans-serif; }}
            .{PFX}-preview table {{ border-collapse: collapse; font-size: 12px; width: 100%; }}
            .{PFX}-preview th, .{PFX}-preview td {{ border: 1px solid #262B36; padding: 4px 8px; text-align: left; }}
            .{PFX}-preview th {{ background: #0B0D11; color: #8A92A6; font-weight: 600; text-transform: uppercase; font-size: 10px; }}
            .{PFX}-load {{ margin-top: 10px; background: #0B0D11; border: 1px solid #E8B339; color: #E8B339; border-radius: 4px; padding: 6px 10px; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11px; cursor: pointer; }}
            .{PFX}-load:hover {{ background: #1c212b; }}
            .{PFX}-live[data-loading="1"] {{ opacity: 0.5; }}
        </style>
        """

    # ----- node/edge markup --------------------------------------------

    def _canvas_size(self):
        if not self.layout:
            return PAD * 2, PAD * 2
        max_col = max(c for c, _ in self.layout.values())
        max_row = max(r for _, r in self.layout.values())
        width = PAD * 2 + max_col * COL_W + NODE_W
        height = PAD * 2 + max_row * ROW_H + NODE_H
        return width, height

    def _node_center(self, node_id: str):
        col, row = self.layout[node_id]
        x = PAD + col * COL_W
        y = PAD + row * ROW_H
        return x, y

    def _render_node_button(self, node: LineageNode) -> str:
        x, y = self._node_center(node.node_id)
        classes = [f"{PFX}-node"]
        if node.is_base:
            classes.append("is-base")
        if node.is_error:
            classes.append("is-error")
        name = html.escape(node.label)
        shape = html.escape(_cols_str(node))
        return f"""
        <button type="button" id="{PFX}-{node.node_id}"
                class="{' '.join(classes)}" role="tab" aria-selected="false"
                aria-controls="{PFX}-panel" tabindex="-1"
                style="left:{x}px; top:{y}px;" data-node-id="{node.node_id}">
            <div class="{PFX}-node-name">{name}</div>
            <div class="{PFX}-node-shape">{shape}</div>
        </button>
        """

    def _render_edges_svg(self, width: int, height: int) -> str:
        lines = []
        for node in self.graph.nodes.values():
            is_join = len(node.parent_ids) > 1
            cx, cy = self._node_center(node.node_id)
            child_y = cy + NODE_H / 2
            for parent_id in node.parent_ids:
                px, py = self._node_center(parent_id)
                parent_right = px + NODE_W
                parent_mid_y = py + NODE_H / 2
                cls = "join" if is_join else ""
                lines.append(
                    f'<line class="{PFX}-edge {cls}" x1="{parent_right}" y1="{parent_mid_y}" '
                    f'x2="{cx}" y2="{child_y}" />'
                )
        return f'<svg width="{width}" height="{height}">{"".join(lines)}</svg>'

    # ----- detail panel --------------------------------------------------

    def _render_detail(self, node: LineageNode, interactive: bool) -> str:
        code = html.escape(node.code_snippet)
        op_label = html.escape(node.operation_name or ("input" if node.is_base else node.node_id))

        cols_chip = ""
        dtypes_html = ""
        if node.metadata is not None:
            cols_chip = f'<span class="{PFX}-chip">cols <b>{len(node.metadata.columns)}</b></span>'
            items = "".join(
                f"<span><b>{html.escape(c)}</b>: {html.escape(t)}</span>"
                for c, t in node.metadata.dtypes.items()
            )
            dtypes_html = f'<div class="{PFX}-dtypes">{items}</div>'

        time_chip = ""
        if node.execution_time_ms is not None:
            time_chip = f'<span class="{PFX}-chip">⏱ <b>{node.execution_time_ms:.2f}</b> ms</span>'

        err_html = ""
        if node.error:
            err_html = f'<div class="{PFX}-err">❌ {html.escape(node.error)}</div>'

        live_html = self._render_live_block(node, interactive)

        return f"""
        <div class="{PFX}-panel-grid">
            <div>
                <h4>{html.escape(node.node_id)} · {op_label}</h4>
                <div class="{PFX}-code">{code}</div>
                <div class="{PFX}-metrics">{cols_chip}{time_chip}</div>
                {dtypes_html}
                {err_html}
            </div>
            <div>{live_html}</div>
        </div>
        """

    def _render_live_block(self, node: LineageNode, interactive: bool) -> str:
        """The part of the detail panel that depends on row_count/preview.
        In eager mode these are already computed; in interactive mode they
        show a button until the widget layer fills them in on demand."""
        if not interactive:
            row_chip = f'<span class="{PFX}-chip">righe <b>{compute_row_count(node)}</b></span>'
            preview = compute_preview_html(node)
            preview_html = f'<div class="{PFX}-preview">{preview}</div>' if preview else \
                f'<div class="{PFX}-dtypes">nessuna anteprima disponibile</div>'
            return f'<h4>anteprima</h4><div class="{PFX}-metrics">{row_chip}</div>{preview_html}'

        if node.row_count is not None:
            row_chip = f'<span class="{PFX}-chip">righe <b>{node.row_count}</b></span>'
            preview_html = f'<div class="{PFX}-preview">{node.preview_html or ""}</div>'
            return f'<h4>anteprima</h4><div class="{PFX}-metrics">{row_chip}</div>{preview_html}'

        return (
            f'<h4>anteprima</h4>'
            f'<div class="{PFX}-live" data-node-id="{node.node_id}" data-loading="0">'
            f'<button type="button" class="{PFX}-load" data-node-id="{node.node_id}">'
            f'Calcola righe e anteprima</button></div>'
        )

    # ----- top-level render -----------------------------------------------

    def _body(self, interactive: bool) -> str:
        width, height = self._canvas_size()
        nodes_html = "".join(self._render_node_button(n) for n in self.graph.nodes.values())
        edges_svg = self._render_edges_svg(width, height)

        err_banner = f'<div class="{PFX}-err">❌ {html.escape(self.graph.error)}</div>' if self.graph.error else ""
        n_nodes = len(self.graph.nodes)
        header_html = f"""
        <div class="{PFX}-header">
            <div class="{PFX}-title"><span class="dot">●</span>etl / lineage graph</div>
            <div class="{PFX}-meta"><b>{n_nodes}</b> nodes · <b>{self.graph.total_time_ms:.2f}</b> ms total</div>
        </div>
        """

        canvas_html = f"""
        <div class="{PFX}-canvas" role="tablist" aria-label="ETL lineage graph"
             style="width:{width}px; height:{height}px;">
            {edges_svg}
            {nodes_html}
        </div>
        """

        panel_html = f'<div id="{PFX}-panel" class="{PFX}-panel" role="tabpanel" tabindex="0"></div>'

        return f"""
        <div class="{PFX}-root" data-interactive="{"1" if interactive else "0"}">
            {header_html}
            {err_banner}
            {canvas_html}
            {panel_html}
        </div>
        """

    def render_skeleton(self) -> str:
        """Bare markup for the widget layer: cheap metadata only, no inline
        JS (the widget's own JS drives interactivity via anywidget's comm)."""
        return f"{self._css()}{self._body(interactive=True)}"

    def detail_html_by_node(self, interactive: bool) -> dict:
        return {n.node_id: self._render_detail(n, interactive) for n in self.graph.nodes.values()}

    def render_static(self, eager_details: bool = True) -> HTML:
        """Self-contained static render with inline JS tab behavior. Used
        whenever no live Python<->JS channel is available (scripts, tests,
        notebook export)."""
        details = self.detail_html_by_node(interactive=not eager_details)
        details_json = json.dumps(details)

        js = f"""
        <script>
        (function() {{
            const roots = document.querySelectorAll('.{PFX}-root[data-interactive="0"]');
            roots.forEach(initRoot);
            function initRoot(root) {{
                if (root.dataset.etlInit === '1') return;
                root.dataset.etlInit = '1';
                const tabs = Array.from(root.querySelectorAll('.{PFX}-node'));
                const panel = root.querySelector('.{PFX}-panel');
                const details = {details_json};
                function select(i) {{
                    tabs.forEach((t, j) => t.setAttribute('aria-selected', j === i ? 'true' : 'false'));
                    panel.innerHTML = details[tabs[i].dataset.nodeId] || '';
                    panel.classList.add('is-open');
                }}
                tabs.forEach((t, i) => t.addEventListener('click', () => select(i)));
                if (tabs.length) select(0);
            }}
        }})();
        </script>
        """
        return HTML(f"{self._css()}{self._body(interactive=False)}{js}")
