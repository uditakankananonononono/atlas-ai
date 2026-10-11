"""Conservative, offline local-variable alpha-renaming for Python source.

No submitted code is executed. Only a single plain function in a restricted
syntax subset is accepted. This is not a general Python refactoring engine.
"""
from __future__ import annotations
import ast
import copy
import hashlib
import keyword
import re

_ALLOWED = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg,
    ast.Assign, ast.AugAssign, ast.Return, ast.If, ast.For, ast.While,
    ast.Break, ast.Continue, ast.Pass, ast.Expr,
    ast.Name, ast.Constant, ast.Load, ast.Store,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Subscript, ast.Slice,
    ast.operator, ast.unaryop, ast.boolop, ast.cmpop,
)


def _identifier(value: str) -> bool:
    return (isinstance(value, str) and
            re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', value) is not None and
            not keyword.iskeyword(value))


class _Rename(ast.NodeTransformer):
    def __init__(self, old: str, new: str):
        self.old, self.new = old, new
        self.count = 0

    def visit_Name(self, node: ast.Name):
        if node.id == self.old:
            self.count += 1
            node.id = self.new
        return node


def rename_local(source: str, old: str, new: str) -> dict:
    """Return transformed source, hashes and structural verification evidence.

    Reject unsupported syntax instead of guessing whether reflection, closures,
    argument binding or imports would preserve behavior. Never edit a repository.
    Comments/formatting are not preserved by ast.unparse. Tracebacks and locals
    visible to an external debugger can differ; ordinary runtime values and
    exceptions are the behavior boundary of this source transformation.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError('source must be nonempty Python text')
    if not _identifier(old) or not _identifier(new) or old == new:
        raise ValueError('distinct ASCII non-keyword identifiers required')
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as exc:
        raise ValueError('invalid Python source') from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('exactly one plain function required')
    function = tree.body[0]
    if (function.decorator_list or function.returns or
            function.args.defaults or function.args.kw_defaults or
            function.args.vararg or function.args.kwarg):
        raise ValueError('decorators, annotations, defaults and variadics unsupported')
    parameters = list(function.args.posonlyargs) + list(function.args.args) + list(function.args.kwonlyargs)
    if any(arg.annotation for arg in parameters):
        raise ValueError('annotations unsupported')
    if old in {arg.arg for arg in parameters} or new in {arg.arg for arg in parameters}:
        raise ValueError('cannot rename or collide with a parameter')
    if function.name in {old, new}:
        raise ValueError('cannot collide with function binding')
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError('unsupported syntax: ' + type(node).__name__)
        if isinstance(node, ast.FunctionDef) and node is not function:
            raise ValueError('nested functions unsupported')
    names = [node for node in ast.walk(function) if isinstance(node, ast.Name)]
    if any(node.id == new for node in names):
        raise ValueError('replacement already occurs in function')
    if not any(node.id == old and isinstance(node.ctx, ast.Store) for node in names):
        raise ValueError('old identifier is not a local assignment target')
    updated = copy.deepcopy(tree)
    transformer = _Rename(old, new)
    transformer.visit(updated)
    ast.fix_missing_locations(updated)
    text = ast.unparse(updated) + '\n'
    reparsed = ast.parse(text)
    inverse = copy.deepcopy(reparsed)
    _Rename(new, old).visit(inverse)
    if ast.dump(inverse, include_attributes=False) != ast.dump(tree, include_attributes=False):
        raise ValueError('alpha-equivalence verification failed')
    compile(reparsed, '<refactored>', 'exec')
    return {
        'source': text,
        'renamed_occurrences': transformer.count,
        'before_sha256': hashlib.sha256(source.encode('utf-8')).hexdigest(),
        'after_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'ast_alpha_equivalence_checked': True,
        'repository_behavior_verified': False,
        'boundary': 'Restricted single-function local rename; no execution, file write, merge or release.',
    }
