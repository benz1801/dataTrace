import anywidget
import traitlets

from ..core.adapters import compute_preview_html, compute_row_count
from ..core.models import LineageGraph
from .renderer import StaticGraphRenderer

_ESM = r"""
function render({ model, el }) {
    el.innerHTML = model.get("graph_html");
    const cache = {};

    function wireLoadButton(panel, nodeId) {
        const loadBtn = panel.querySelector(".etl-graph-load");
        if (loadBtn) {
            loadBtn.addEventListener("click", () => {
                model.send({ type: "request_data", node_id: nodeId });
                loadBtn.textContent = "Calcolo in corso…";
                loadBtn.disabled = true;
            });
        }
    }

    function selectNode(nodeId) {
        el.querySelectorAll(".etl-graph-node").forEach((b) => {
            b.setAttribute("aria-selected", b.dataset.nodeId === nodeId ? "true" : "false");
        });
        const panel = el.querySelector(".etl-graph-panel");
        panel.dataset.currentNode = nodeId;
        panel.classList.add("is-open");
        if (cache[nodeId]) {
            panel.innerHTML = cache[nodeId];
            wireLoadButton(panel, nodeId);
            return;
        }
        panel.innerHTML = '<div class="etl-graph-dtypes">caricamento…</div>';
        model.send({ type: "request_detail", node_id: nodeId });
    }

    el.querySelectorAll(".etl-graph-node").forEach((btn) => {
        btn.addEventListener("click", () => selectNode(btn.dataset.nodeId));
    });

    model.on("msg:custom", (msg) => {
        const panel = el.querySelector(".etl-graph-panel");
        if (!panel) return;
        cache[msg.node_id] = msg.html;
        if (panel.dataset.currentNode !== msg.node_id) return;
        panel.innerHTML = msg.html;
        wireLoadButton(panel, msg.node_id);
    });
}
export default { render };
"""


class LineageWidget(anywidget.AnyWidget):
    """Interactive lineage graph with on-demand row-count/preview.

    The initial `graph_html` skeleton only carries cheap metadata
    (columns/dtypes), computed eagerly by the executor. Clicking a node asks
    Python (over the widget comm) for its detail panel; clicking "Calcola
    righe e anteprima" inside that panel is what actually triggers
    `compute_row_count`/`compute_preview_html` -- so an expensive read (e.g.
    a Spark `.count()` once that backend exists) only ever runs for a node
    the user explicitly asked about.
    """

    _esm = _ESM
    graph_html = traitlets.Unicode("").tag(sync=True)

    def __init__(self, graph: LineageGraph, **kwargs):
        super().__init__(**kwargs)
        # Strong reference: keeps node.ref (the real DataFrame objects) alive
        # for the lifetime of the widget, so later clicks can still compute
        # row_count/preview even after the cell that created them finished.
        self._graph = graph
        self._renderer = StaticGraphRenderer(graph)
        self.graph_html = self._renderer.render_skeleton()
        self.on_msg(self._handle_msg)

    def _handle_msg(self, widget, content, buffers):
        node_id = content.get("node_id")
        if node_id not in self._graph.nodes:
            return
        node = self._graph.get(node_id)
        msg_type = content.get("type")

        if msg_type == "request_detail":
            self.send({
                "type": "detail_response",
                "node_id": node_id,
                "html": self._renderer._render_detail(node, interactive=True),
            })
        elif msg_type == "request_data":
            compute_row_count(node)
            compute_preview_html(node)
            self.send({
                "type": "data_response",
                "node_id": node_id,
                "html": self._renderer._render_detail(node, interactive=True),
            })
