import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class JoinBinding:
    """Records that a call argument at `path` references another tracked
    table, making the resulting node depend on `parent_id` as a second
    (or further) parent -- e.g. the `other` argument of `.merge(other, ...)`.
    `path` is `[index]` for a positional arg or `[keyword_name]` for a kwarg.
    """
    path: list
    parent_id: str


@dataclass
class PlannedNode:
    node_id: str
    ast_node: ast.AST
    primary_parent: Optional[str] = None
    join_bindings: List[JoinBinding] = field(default_factory=list)
    operation_name: Optional[str] = None
    origin_var: Optional[str] = None
    is_base: bool = False


@dataclass
class ParsedChain:
    nodes: List[PlannedNode]
    statement_outputs: List[str]


def _step_into(node: ast.AST) -> Optional[ast.AST]:
    """Move one level toward the base of a method-chain expression.

    Only follows chains built from attribute access (`x.attr`) and method
    calls on an attribute (`x.method(...)`). A call whose function is not an
    attribute (e.g. a bare `helper(x)`) has no further base to walk into --
    it is treated as an opaque base expression instead of crashing.
    """
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.value
        return None
    if isinstance(node, ast.Attribute):
        return node.value
    return None


def _find_name_refs(expr: ast.AST) -> List[ast.Name]:
    """Find variable references inside a call argument, so that
    `.merge(other, on=...)` or `pd.concat([a, b])`-style list arguments can be
    recognized as pointing at other tracked tables."""
    if isinstance(expr, ast.Name):
        return [expr]
    if isinstance(expr, (ast.List, ast.Tuple)):
        refs: List[ast.Name] = []
        for elt in expr.elts:
            refs.extend(_find_name_refs(elt))
        return refs
    return []


class ChainParser:
    """Parses Python code into a lineage graph plan.

    Walks every `Assign`/`Expr` statement in the cell (not just the first),
    tracking a variable -> node_id symbol table so that later statements can
    reference tables produced earlier in the same cell -- either as the base
    of a new chain or as a join/merge argument (which becomes a second
    parent). Statements not resolvable to `ast.Name` (e.g. a bare function
    call as the base) become an opaque base node instead of failing.
    """

    def __init__(self, code: str):
        self.code = code
        self.tree = ast.parse(code)

    def extract_lineage(self) -> ParsedChain:
        symbol_table: Dict[str, str] = {}
        nodes: List[PlannedNode] = []
        statement_outputs: List[str] = []
        counter = 0

        def next_id() -> str:
            nonlocal counter
            node_id = f"n{counter}"
            counter += 1
            return node_id

        def resolve_or_create_base(name: str) -> str:
            if name in symbol_table:
                return symbol_table[name]
            node_id = next_id()
            nodes.append(PlannedNode(
                node_id=node_id,
                ast_node=ast.Name(id=name, ctx=ast.Load()),
                origin_var=name,
                is_base=True,
            ))
            symbol_table[name] = node_id
            return node_id

        for stmt in self.tree.body:
            if isinstance(stmt, ast.Assign):
                value = stmt.value
            elif isinstance(stmt, ast.Expr):
                value = stmt.value
            else:
                continue

            chain_ast_nodes: List[ast.AST] = []
            current = value
            while True:
                stepped = _step_into(current)
                if stepped is None:
                    base_expr = current
                    break
                chain_ast_nodes.append(current)
                current = stepped
            chain_ast_nodes.reverse()  # base-adjacent first, outermost last

            simple_target = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                    and isinstance(stmt.targets[0], ast.Name):
                simple_target = stmt.targets[0].id

            if not chain_ast_nodes:
                # No transformation happened (e.g. `x = df` or `x = 5`).
                if simple_target is not None and isinstance(base_expr, ast.Name):
                    symbol_table[simple_target] = resolve_or_create_base(base_expr.id)
                continue

            if isinstance(base_expr, ast.Name):
                prev_id = resolve_or_create_base(base_expr.id)
            else:
                prev_id = next_id()
                nodes.append(PlannedNode(node_id=prev_id, ast_node=base_expr, is_base=True))

            for chain_node in chain_ast_nodes:
                node_id = next_id()
                join_bindings: List[JoinBinding] = []
                operation_name = None

                if isinstance(chain_node, ast.Call):
                    if isinstance(chain_node.func, ast.Attribute):
                        operation_name = chain_node.func.attr
                    for i, arg in enumerate(chain_node.args):
                        for ref in _find_name_refs(arg):
                            join_bindings.append(JoinBinding(
                                path=[i], parent_id=resolve_or_create_base(ref.id),
                            ))
                    for kw in chain_node.keywords:
                        if kw.arg is None:
                            continue
                        for ref in _find_name_refs(kw.value):
                            join_bindings.append(JoinBinding(
                                path=[kw.arg], parent_id=resolve_or_create_base(ref.id),
                            ))
                elif isinstance(chain_node, ast.Attribute):
                    operation_name = chain_node.attr

                nodes.append(PlannedNode(
                    node_id=node_id,
                    ast_node=chain_node,
                    primary_parent=prev_id,
                    join_bindings=join_bindings,
                    operation_name=operation_name,
                ))
                prev_id = node_id

            if simple_target is not None:
                symbol_table[simple_target] = prev_id
                nodes[-1].origin_var = simple_target

            statement_outputs.append(prev_id)

        return ParsedChain(nodes=nodes, statement_outputs=statement_outputs)
