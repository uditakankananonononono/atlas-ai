"""Static source structure only. Never imports or executes inspected modules."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re

_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z_0-9]*\Z')


@dataclass(frozen=True)
class SourceResult:
    structural_source_match: bool
    reason: str
    source_path: str | None = None
    node_path: tuple[str, ...] = ()
    parameter_suffix_present: bool = False
    parameter_case_verified: bool = False


def _paths(body: list[ast.stmt], prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    """Only direct module/class declarations; never descend into functions.

    Conditional declarations, inherited members, aliases and dynamic generation
    are outside this static contract. Repeated declarations or assignments to a
    declaration's name are ambiguous and excluded, not resolved by runtime guess.
    """
    result: set[tuple[str, ...]] = set()
    bindings: dict[str, int] = {}
    for statement in body:
        names: set[str] = set()
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(statement.name)
        elif isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                names.update(node.id for node in ast.walk(target) if isinstance(node, ast.Name))
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or (alias.name.split('.')[0] if isinstance(statement, ast.Import)
                                         else alias.name) for alias in statement.names)
        for name in names:
            bindings[name] = bindings.get(name, 0) + 1
    for statement in body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if statement.name.startswith('test_') and bindings[statement.name] == 1:
                result.add(prefix + (statement.name,))
        elif isinstance(statement, ast.ClassDef) and bindings[statement.name] == 1:
            result.update(_paths(statement.body, prefix + (statement.name,)))
    return result


def structural_paths(source: str) -> frozenset[tuple[str, ...]]:
    """Index explicit source declaration paths. ast.parse only; no evaluation.

    SyntaxError is intentionally left visible to callers of this text primitive.
    These paths say nothing about pytest collection, decorators or execution.
    """
    return frozenset(_paths(ast.parse(source).body))


def validate_reference(reference: str, *, root: Path) -> SourceResult:
    """Check root-contained relative filename::class...::test_name syntax.

    One nonempty final [parameter-id] suffix is accepted syntactically, never
    checked for existence. Nested brackets/newlines and :: inside IDs are outside
    this conservative grammar. Paths escaping root (including symlinks) fail.
    Files are decoded as UTF-8 with optional BOM; no environment, imports or test execution.
    """
    if not isinstance(reference, str) or '\n' in reference or '\r' in reference:
        return SourceResult(False, 'malformed_reference')
    parts = reference.split('::')
    if len(parts) < 2 or not parts[0] or any(not part for part in parts[1:]):
        return SourceResult(False, 'malformed_reference')
    filename, *nodes = parts
    suffix = False
    final = nodes[-1]
    if '[' in final or ']' in final:
        match = re.fullmatch(r'([^\[\]]+)\[([^\[\]\r\n]+)\]', final)
        if match is None:
            return SourceResult(False, 'malformed_reference')
        nodes[-1] = match.group(1)
        suffix = True
    if any(_IDENTIFIER.fullmatch(node) is None for node in nodes) or not nodes[-1].startswith('test_'):
        return SourceResult(False, 'malformed_reference')
    node_path = tuple(nodes)
    path = Path(filename)
    if path.is_absolute() or path.suffix != '.py' or '..' in path.parts:
        return SourceResult(False, 'malformed_reference', filename, node_path, suffix)
    try:
        base = Path(root).resolve()
        path = (base / path).resolve()
        if not path.is_relative_to(base):
            return SourceResult(False, 'source_path_outside_root', filename, node_path, suffix)
        if not path.exists():
            return SourceResult(False, 'source_missing', filename, node_path, suffix)
        if not path.is_file():
            return SourceResult(False, 'source_not_regular_file', filename, node_path, suffix)
        source = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        return SourceResult(False, 'source_decode_error', filename, node_path, suffix)
    except ValueError:
        return SourceResult(False, 'malformed_reference', filename, node_path, suffix)
    except (OSError, RuntimeError):
        return SourceResult(False, 'source_unreadable', filename, node_path, suffix)
    try:
        paths = structural_paths(source)
    except (SyntaxError, ValueError):
        return SourceResult(False, 'source_syntax_invalid', filename, node_path, suffix)
    matched = node_path in paths
    return SourceResult(matched, 'structural_source_match' if matched else 'node_path_not_found',
                        filename, node_path, suffix)
