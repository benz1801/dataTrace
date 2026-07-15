from IPython.display import HTML
import html
from ..core.models import ChainResult, StepResult, DataFrameState


def _shape_str(state: DataFrameState) -> str:
    """Render a shape as 'R × C' (unicode multiplication sign)."""
    if state is None:
        return "—"
    rows, cols = state.shape
    return f"{rows}×{cols}"


def _delta_text(before: DataFrameState, after: DataFrameState) -> str:
    """Build the diff-in-the-connector text. Returns empty string if no change."""
    if before is None or after is None:
        return ""
    rb, cb = before.shape
    ra, ca = after.shape
    row_d = ra - rb
    col_d = ca - cb
    parts = []
    if row_d != 0:
        sign = "+" if row_d > 0 else "−"  # minus sign (U+2212), not hyphen
        parts.append(f"{sign}{abs(row_d)} rows")
    if col_d != 0:
        sign = "+" if col_d > 0 else "−"
        parts.append(f"{sign}{abs(col_d)} cols")
    return " · ".join(parts)


def _delta_class(before: DataFrameState, after: DataFrameState) -> str:
    """Classify the connector as positive/negative/neutral."""
    if before is None or after is None:
        return "neutral"
    rb, cb = before.shape
    ra, ca = after.shape
    if ra < rb or ca < cb:
        return "negative"
    if ra > rb or ca > cb:
        return "positive"
    return "neutral"


class HTMLRenderer:
    """Renders ChainResult as a horizontal pipeline visualization for Jupyter.

    Layout:
      [base node] ─▶[step 1] ─▶[step 2] ─▶ ...
      The arrow between two nodes carries the shape diff inline (signature element).

    Interaction:
      - Click a node to expand its detail panel below the timeline.
      - Keyboard: ← / → moves focus, Enter expands, Esc closes.
      - ARIA: role=tablist on the timeline, role=tab on each node, role=tabpanel on the detail.
    """

    # Class prefix used everywhere: keeps our CSS out of Jupyter's own theme.
    PFX = "etl-pipe"

    def __init__(self, result: ChainResult):
        self.result = result

    # ----- CSS ------------------------------------------------------------

    def _generate_css(self) -> str:
        return f"""
        <style>
            .{self.PFX}-root {{
                font-family: 'Inter', 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
                background: #0F1115;
                color: #E6E8EC;
                border: 1px solid #262B36;
                border-radius: 8px;
                padding: 18px 20px 16px;
                margin: 10px 0;
                font-size: 13px;
                line-height: 1.45;
            }}
            .{self.PFX}-header {{
                display: flex;
                align-items: baseline;
                justify-content: space-between;
                gap: 12px;
                margin-bottom: 16px;
                padding-bottom: 10px;
                border-bottom: 1px solid #262B36;
            }}
            .{self.PFX}-title {{
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 0.02em;
                color: #E6E8EC;
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, 'Cascadia Mono', monospace;
            }}
            .{self.PFX}-title .dot {{
                color: #E8B339;
                margin-right: 6px;
            }}
            .{self.PFX}-meta {{
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
                font-size: 11px;
                color: #8A92A6;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }}
            .{self.PFX}-meta b {{
                color: #E6E8EC;
                font-weight: 600;
            }}

            .{self.PFX}-err {{
                background: rgba(232, 74, 74, 0.08);
                border-left: 3px solid #E84A4A;
                color: #E84A4A;
                padding: 10px 14px;
                border-radius: 4px;
                font-family: 'JetBrains Mono', ui-monospace, monospace;
                font-size: 12px;
                margin-bottom: 14px;
            }}

            /* Timeline */
            .{self.PFX}-timeline {{
                display: flex;
                align-items: stretch;
                overflow-x: auto;
                padding: 4px 0 12px;
                scroll-snap-type: x proximity;
            }}
            .{self.PFX}-timeline::-webkit-scrollbar {{ height: 6px; }}
            .{self.PFX}-timeline::-webkit-scrollbar-thumb {{ background: #262B36; border-radius: 3px; }}

            .{self.PFX}-node {{
                scroll-snap-align: start;
                appearance: none;
                background: #181C24;
                border: 1px solid #262B36;
                border-radius: 6px;
                padding: 10px 12px;
                min-width: 130px;
                text-align: left;
                cursor: pointer;
                font: inherit;
                color: inherit;
                transition: border-color 120ms ease, box-shadow 120ms ease, background 120ms ease;
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}
            .{self.PFX}-node:hover {{
                border-color: #3a4150;
                background: #1c212b;
            }}
            .{self.PFX}-node:focus-visible {{
                outline: none;
                border-color: #E8B339;
                box-shadow: 0 0 0 2px rgba(232, 179, 57, 0.25);
            }}
            .{self.PFX}-node[aria-selected="true"] {{
                border-color: #E8B339;
                box-shadow: 0 0 0 1.5px #E8B339;
                background: #1c212b;
            }}
            .{self.PFX}-node.is-base {{
                border-style: dashed;
            }}
            .{self.PFX}-node-num {{
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
                font-size: 10px;
                color: #8A92A6;
                letter-spacing: 0.1em;
                text-transform: uppercase;
            }}
            .{self.PFX}-node-name {{
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
                font-size: 13px;
                color: #E6E8EC;
                font-weight: 600;
            }}
            .{self.PFX}-node-shape {{
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
                font-size: 11px;
                color: #8A92A6;
            }}
            .{self.PFX}-node-time {{
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
                font-size: 10px;
                color: #8A92A6;
                margin-top: 2px;
            }}
            .{self.PFX}-node.is-base .{self.PFX}-node-name {{ color: #E8B339; }}

            /* Connectors (signature: diff-in-the-connector) */
            .{self.PFX}-conn {{
                display: flex;
                align-items: center;
                padding: 0 6px;
                color: #E8B339;
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
                font-size: 11px;
                white-space: nowrap;
                min-width: 56px;
            }}
            .{self.PFX}-conn .arrow {{ font-size: 14px; line-height: 1; }}
            .{self.PFX}-conn .delta {{ margin: 0 4px; }}
            .{self.PFX}-conn.positive .delta {{ color: #5FB87A; }}
            .{self.PFX}-conn.negative .delta {{ color: #E07B7B; }}
            .{self.PFX}-conn.neutral .delta {{ color: #4a5060; }}
            .{self.PFX}-conn.neutral .arrow {{ color: #4a5060; }}

            /* Detail panel */
            .{self.PFX}-panel {{
                display: none;
                background: #181C24;
                border: 1px solid #262B36;
                border-radius: 6px;
                padding: 14px 16px;
                margin-top: 4px;
            }}
            .{self.PFX}-panel.is-open {{ display: block; }}
            .{self.PFX}-panel-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
            }}
            @media (max-width: 720px) {{
                .{self.PFX}-panel-grid {{ grid-template-columns: 1fr; }}
            }}
            .{self.PFX}-panel h4 {{
                font-size: 11px;
                color: #8A92A6;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin: 0 0 8px;
                font-weight: 600;
            }}
            .{self.PFX}-code {{
                background: #0B0D11;
                border: 1px solid #262B36;
                border-radius: 4px;
                padding: 10px 12px;
                font-family: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;
                font-size: 12px;
                color: #E6E8EC;
                overflow-x: auto;
                white-space: pre;
                line-height: 1.5;
            }}
            .{self.PFX}-metrics {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                margin-top: 4px;
            }}
            .{self.PFX}-chip {{
                font-family: 'JetBrains Mono', ui-monospace, monospace;
                font-size: 11px;
                background: #0B0D11;
                border: 1px solid #262B36;
                border-radius: 4px;
                padding: 4px 8px;
                color: #E6E8EC;
            }}
            .{self.PFX}-chip b {{ color: #E8B339; font-weight: 600; }}
            .{self.PFX}-chip.pos {{ border-color: rgba(95, 184, 122, 0.4); }}
            .{self.PFX}-chip.neg {{ border-color: rgba(224, 123, 123, 0.4); }}
            .{self.PFX}-dtypes {{
                font-family: 'JetBrains Mono', ui-monospace, monospace;
                font-size: 11px;
                color: #8A92A6;
                margin-top: 8px;
                max-height: 120px;
                overflow-y: auto;
            }}
            .{self.PFX}-dtypes span {{ display: inline-block; margin-right: 12px; }}
            .{self.PFX}-dtypes b {{ color: #E6E8EC; }}
            .{self.PFX}-preview {{
                margin-top: 12px;
                overflow-x: auto;
                font-family: 'Inter', system-ui, sans-serif;
            }}
            .{self.PFX}-preview table {{
                border-collapse: collapse;
                font-size: 12px;
                width: 100%;
            }}
            .{self.PFX}-preview th, .{self.PFX}-preview td {{
                border: 1px solid #262B36;
                padding: 4px 8px;
                text-align: left;
            }}
            .{self.PFX}-preview th {{
                background: #0B0D11;
                color: #8A92A6;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 10px;
                letter-spacing: 0.05em;
            }}
            .{self.PFX}-preview td {{ color: #E6E8EC; }}

            @media (prefers-reduced-motion: reduce) {{
                .{self.PFX}-node {{ transition: none; }}
            }}
        </style>
        """

    # ----- Per-step rendering --------------------------------------------

    def _render_node_button(
        self, *, node_id: str, index_label: str, op_name: str, shape: str,
        time_ms: float | None, is_base: bool, is_error: bool,
    ) -> str:
        time_html = ""
        if time_ms is not None:
            time_html = f'<div class="{self.PFX}-node-time">⏱ {time_ms:.2f} ms</div>'

        error_class = f' {self.PFX}-node-error' if is_error else ""
        base_class = f' {self.PFX}-is-base' if is_base else ""
        return f"""
        <button type="button"
                id="{node_id}"
                class="{self.PFX}-node{base_class}{error_class}"
                role="tab"
                aria-selected="false"
                aria-controls="{self.PFX}-panel"
                tabindex="-1">
            <div class="{self.PFX}-node-num">{index_label}</div>
            <div class="{self.PFX}-node-name">{html.escape(op_name)}</div>
            <div class="{self.PFX}-node-shape">{html.escape(shape)}</div>
            {time_html}
        </button>
        """

    def _render_connector(self, *, before: DataFrameState, after: DataFrameState) -> str:
        # If either side is missing (e.g. groupby returns a DataFrameGroupBy, not
        # a DataFrame, and the executor can't capture its shape), fall back to a
        # neutral "no diff available" indicator instead of a misleading number.
        if before is None or after is None:
            return f"""
            <div class="{self.PFX}-conn neutral" aria-hidden="true">
                <span class="delta">·</span>
                <span class="arrow">▶</span>
            </div>
            """
        cls = _delta_class(before, after)
        delta = _delta_text(before, after)
        delta_html = f'<span class="delta">{html.escape(delta)}</span>' if delta else ''
        return f"""
        <div class="{self.PFX}-conn {cls}" aria-hidden="true">
            {delta_html}
            <span class="arrow">▶</span>
        </div>
        """

    def _render_detail(self, step: StepResult | None, is_base: bool, base_name: str | None) -> str:
        """Render the (hidden by default) detail panel content for the currently active step."""
        if is_base:
            op_label = "input"
            code = base_name or "input"
            state = self.result.base_state
            time_ms = None
            index_label = "BASE"
        else:
            assert step is not None
            op_label = step.operation_name
            code = step.code_snippet
            state = step.state_after
            time_ms = step.execution_time_ms
            index_label = f"step {step.step_index}"

        if state is None:
            shape_chip = '<span class="' + self.PFX + '-chip">no dataframe</span>'
        else:
            shape_chip = f'<span class="{self.PFX}-chip">shape <b>{_shape_str(state)}</b></span>'

        time_chip = ""
        if time_ms is not None:
            time_chip = f'<span class="{self.PFX}-chip">⏱ <b>{time_ms:.2f}</b> ms</span>'

        # Shape diff vs previous (only meaningful for non-base)
        diff_chips = ""
        if not is_base and step is not None and step.state_before and step.state_after:
            rb, cb = step.state_before.shape
            ra, ca = step.state_after.shape
            row_d = ra - rb
            col_d = ca - cb
            if row_d != 0:
                cls = "pos" if row_d > 0 else "neg"
                sign = "+" if row_d > 0 else "−"
                diff_chips += f'<span class="{self.PFX}-chip {cls}">rows {sign}{abs(row_d)}</span>'
            if col_d != 0:
                cls = "pos" if col_d > 0 else "neg"
                sign = "+" if col_d > 0 else "−"
                diff_chips += f'<span class="{self.PFX}-chip {cls}">cols {sign}{abs(col_d)}</span>'

        # Dtypes
        dtypes_html = ""
        if state and state.dtypes:
            items = "".join(
                f"<span><b>{html.escape(c)}</b>: {html.escape(t)}</span>"
                for c, t in state.dtypes.items()
            )
            dtypes_html = f'<div class="{self.PFX}-dtypes">{items}</div>'

        # Head preview (HTML produced by pandas)
        preview_html = ""
        if state and state.head_preview:
            preview_html = f'<div class="{self.PFX}-preview">{state.head_preview}</div>'

        # Error inside a step (if any)
        err_html = ""
        if step is not None and step.error:
            err_html = f'<div class="{self.PFX}-err">❌ {html.escape(step.error)}</div>'

        return f"""
        <div class="{self.PFX}-panel-grid">
            <div>
                <h4>{html.escape(index_label)} · {html.escape(op_label)}</h4>
                <div class="{self.PFX}-code">{html.escape(code)}</div>
                <div class="{self.PFX}-metrics">
                    {shape_chip}{time_chip}{diff_chips}
                </div>
                {dtypes_html}
                {err_html}
            </div>
            <div>
                <h4>head preview</h4>
                {preview_html if preview_html else '<div class="' + self.PFX + '-dtypes">no preview available</div>'}
            </div>
        </div>
        """

    # ----- Top-level render ----------------------------------------------

    def render(self) -> HTML:
        # Build timeline items: [base, step1, step2, ...]
        items: list[dict] = []

        # Base node
        if self.result.base_state is not None or self.result.base_object_name:
            items.append({
                "is_base": True,
                "index_label": "INPUT",
                "op_name": self.result.base_object_name or "input",
                "shape": _shape_str(self.result.base_state) if self.result.base_state else "—",
                "time_ms": None,
                "is_error": False,
            })

        # Steps
        for step in self.result.steps:
            items.append({
                "is_base": False,
                "step": step,
                "index_label": f"STEP {step.step_index:02d}",
                "op_name": step.operation_name,
                "shape": _shape_str(step.state_after) if step.state_after else "—",
                "time_ms": step.execution_time_ms,
                "is_error": bool(step.error),
            })

        # Pre-compute connectors: connector i sits between items[i] and items[i+1].
        # For the first connector (input → step1), diff is base_state vs step1.state_after.
        def state_of(it: dict) -> DataFrameState | None:
            if it["is_base"]:
                return self.result.base_state
            return it["step"].state_after  # type: ignore[union-attr]

        # Build timeline HTML
        timeline_parts: list[str] = []
        for i, it in enumerate(items):
            node_id = f"{self.PFX}-n-{i}"
            timeline_parts.append(self._render_node_button(
                node_id=node_id,
                index_label=it["index_label"],
                op_name=it["op_name"],
                shape=it["shape"],
                time_ms=it["time_ms"],
                is_base=it["is_base"],
                is_error=it["is_error"],
            ))
            if i < len(items) - 1:
                before = state_of(it)
                after = state_of(items[i + 1])
                timeline_parts.append(self._render_connector(before=before, after=after))

        timeline_html = f"""
        <div class="{self.PFX}-timeline" role="tablist" aria-label="ETL pipeline steps">
            {''.join(timeline_parts)}
        </div>
        """

        # Build the (initially empty) detail panel. Content is filled by JS on activation.
        panel_html = f"""
        <div id="{self.PFX}-panel"
             class="{self.PFX}-panel"
             role="tabpanel"
             aria-labelledby="{self.PFX}-n-0"
             tabindex="0">
        </div>
        """

        # Error banner (chain-level)
        err_banner = ""
        if self.result.error:
            err_banner = f'<div class="{self.PFX}-err">❌ {html.escape(self.result.error)}</div>'

        # Header
        steps_n = len(self.result.steps)
        total_ms = self.result.total_time_ms
        header_html = f"""
        <div class="{self.PFX}-header">
            <div class="{self.PFX}-title"><span class="dot">●</span>etl / visual chain</div>
            <div class="{self.PFX}-meta">
                <b>{steps_n}</b> steps · <b>{total_ms:.2f}</b> ms total
            </div>
        </div>
        """

        # Pre-rendered detail templates for each node, embedded as JSON for the JS to use.
        # We embed Python-built HTML strings into a JS array via JSON.
        import json
        details = []
        for it in items:
            if it["is_base"]:
                details.append(self._render_detail(
                    step=None, is_base=True, base_name=self.result.base_object_name
                ))
            else:
                details.append(self._render_detail(
                    step=it["step"], is_base=False, base_name=None
                ))
        details_json = json.dumps(details)

        # Inline JS: tablist semantics, click + keyboard nav.
        js = f"""
        <script>
        (function() {{
            const roots = document.querySelectorAll('.{self.PFX}-root');
            roots.forEach(initRoot);
            function initRoot(root) {{
                if (root.dataset.etlInit === '1') return;
                root.dataset.etlInit = '1';
                const tabs = Array.from(root.querySelectorAll('.{self.PFX}-node'));
                const panel = root.querySelector('#{self.PFX}-panel');
                const details = {details_json};
                // Build a map nodeId -> detailsHtml
                const idToDetail = {{}};
                tabs.forEach((t, i) => {{ idToDetail[t.id] = details[i]; }});

                function select(i, expand) {{
                    tabs.forEach((t, j) => {{
                        const selected = (j === i);
                        t.setAttribute('aria-selected', selected ? 'true' : 'false');
                        t.setAttribute('tabindex', selected ? '0' : '-1');
                    }});
                    if (expand) {{
                        panel.innerHTML = idToDetail[tabs[i].id];
                        panel.classList.add('is-open');
                        panel.setAttribute('aria-labelledby', tabs[i].id);
                        // Scroll into view if below the fold
                        const r = panel.getBoundingClientRect();
                        if (r.bottom > window.innerHeight - 20) {{
                            panel.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
                        }}
                    }}
                }}

                tabs.forEach((t, i) => {{
                    t.addEventListener('click', () => select(i, true));
                    t.addEventListener('keydown', (e) => {{
                        if (e.key === 'Enter' || e.key === ' ') {{
                            e.preventDefault();
                            select(i, true);
                        }} else if (e.key === 'ArrowRight') {{
                            e.preventDefault();
                            const next = (i + 1) % tabs.length;
                            tabs[next].focus();
                            select(next, true);
                        }} else if (e.key === 'ArrowLeft') {{
                            e.preventDefault();
                            const prev = (i - 1 + tabs.length) % tabs.length;
                            tabs[prev].focus();
                            select(prev, true);
                        }} else if (e.key === 'Escape') {{
                            panel.classList.remove('is-open');
                            panel.innerHTML = '';
                        }}
                    }});
                }});

                // Open the first tab by default so users immediately see what's inside.
                if (tabs.length) select(0, true);
            }}
        }})();
        </script>
        """

        root_html = f"""
        <div class="{self.PFX}-root">
            {header_html}
            {err_banner}
            {timeline_html}
            {panel_html}
            {js}
        </div>
        """
        return HTML(f"{self._generate_css()}{root_html}")
