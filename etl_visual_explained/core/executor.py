import ast
import copy
import time
from typing import Any, Dict, List

from .adapters import default_registry
from .models import LineageGraph, LineageNode
from .parser import ChainParser, JoinBinding


def _synth_name(node_id: str) -> str:
    return f"__etl_synth_{node_id}"


def _replace_at_path(call_node: ast.Call, path: list, new_node: ast.AST) -> None:
    """Substitute a single top-level positional or keyword argument with
    `new_node`. Only supports a one-level path (an argument that IS a bare
    Name), which covers method-style joins like `.merge(other, on=...)`.
    Arguments that bundle multiple table references inside a single
    list/tuple (e.g. a `pd.concat`-style call) are a known limitation.
    """
    head = path[0]
    if isinstance(head, int):
        call_node.args[head] = new_node
        return
    for kw in call_node.keywords:
        if kw.arg == head:
            kw.value = new_node
            return


def _rebuild_call(original: ast.Call, primary_parent_id: str, join_bindings: List[JoinBinding]) -> ast.Call:
    """Rebuild `<base>.method(...)` as `<synth_parent>.method(...)`, dropping
    the nested sub-chain entirely (that's what avoids re-executing it), and
    substituting any join argument with its own already-computed synthetic
    reference."""
    new_call = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id=_synth_name(primary_parent_id), ctx=ast.Load()),
            attr=original.func.attr,
            ctx=ast.Load(),
        ),
        args=copy.deepcopy(original.args),
        keywords=copy.deepcopy(original.keywords),
    )
    for jb in join_bindings:
        _replace_at_path(new_call, jb.path, ast.Name(id=_synth_name(jb.parent_id), ctx=ast.Load()))
    return new_call


def _rebuild_attribute(original: ast.Attribute, primary_parent_id: str) -> ast.Attribute:
    return ast.Attribute(
        value=ast.Name(id=_synth_name(primary_parent_id), ctx=ast.Load()),
        attr=original.attr,
        ctx=ast.Load(),
    )


def _eval_expr(expr: ast.expr, global_ns: Dict[str, Any], local_ns: Dict[str, Any]) -> Any:
    wrapper = ast.Expression(body=expr)
    ast.fix_missing_locations(wrapper)
    return eval(compile(wrapper, "<etl-lineage>", "eval"), global_ns, local_ns)


class LineageExecutor:
    """Executes a parsed lineage plan in a single pass.

    Each node evaluates exactly one new operation on top of the
    already-computed result of its parent(s) (injected under a synthetic
    name), instead of re-evaluating the whole prefix chain from scratch --
    this is what keeps execution O(n) instead of the O(n^2) re-evaluation the
    previous linear executor did.
    """

    def __init__(self, code: str, local_ns: Dict[str, Any], global_ns: Dict[str, Any]):
        self.code = code
        self.parser = ChainParser(code)
        self.local_ns = local_ns
        self.global_ns = global_ns

    def execute(self) -> LineageGraph:
        graph = LineageGraph(original_code=self.code)
        try:
            parsed = self.parser.extract_lineage()
        except SyntaxError as e:
            graph.error = f"Parse failed: {e}"
            return graph

        # Copy so we never mutate the caller's real namespace with our
        # synthetic step variables.
        eval_ns: Dict[str, Any] = dict(self.local_ns)
        start_total = time.perf_counter()

        for planned in parsed.nodes:
            parent_ids = ([planned.primary_parent] if planned.primary_parent else []) \
                + [jb.parent_id for jb in planned.join_bindings]
            node = LineageNode(
                node_id=planned.node_id,
                label=planned.origin_var or planned.operation_name or planned.node_id,
                code_snippet=ast.unparse(planned.ast_node),
                operation_name=planned.operation_name,
                parent_ids=parent_ids,
                origin_var=planned.origin_var,
                is_base=planned.is_base,
            )
            graph.add_node(node)

            if any(graph.get(pid).is_error for pid in parent_ids):
                node.is_error = True
                node.error = "Skipped: upstream error"
                continue

            try:
                t0 = time.perf_counter()
                if planned.is_base:
                    obj = eval(ast.unparse(planned.ast_node), self.global_ns, eval_ns)
                elif isinstance(planned.ast_node, ast.Call):
                    call_ast = _rebuild_call(planned.ast_node, planned.primary_parent, planned.join_bindings)
                    obj = _eval_expr(call_ast, self.global_ns, eval_ns)
                else:
                    attr_ast = _rebuild_attribute(planned.ast_node, planned.primary_parent)
                    obj = _eval_expr(attr_ast, self.global_ns, eval_ns)
                node.execution_time_ms = (time.perf_counter() - t0) * 1000
                node.ref = obj
                eval_ns[_synth_name(planned.node_id)] = obj

                adapter = default_registry.find(obj)
                if adapter is not None:
                    node.adapter_name = adapter.name
                    node.metadata = adapter.get_cheap_metadata(obj)
                # row_count / preview_html stay None here: computed lazily,
                # only when the UI layer asks for them on click.
            except Exception as e:
                node.is_error = True
                node.error = str(e)

        graph.total_time_ms = (time.perf_counter() - start_total) * 1000
        graph.statement_outputs = parsed.statement_outputs
        return graph
