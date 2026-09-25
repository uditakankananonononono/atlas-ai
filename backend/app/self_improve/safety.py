"""Static safety validation for synthesized feature code.

Generated code comes from our own templates, but every byte still passes
this scanner before it is written to disk, tested, or activated. A feature
that fails validation is dead on arrival - it can never reach the registry.
"""
from __future__ import annotations

import ast

ALLOWED_IMPORTS = frozenset({"re", "json", "math", "statistics", "datetime", "collections"})
FORBIDDEN_NAMES = frozenset({
    "exec", "eval", "open", "compile", "__import__", "input", "globals",
    "locals", "vars", "getattr", "setattr", "delattr", "exit", "quit",
    "breakpoint", "memoryview", "iter", "help", "print",
})


class SafetyViolation(ValueError):
    pass


def validate_source(source: str, *, allowed_imports: frozenset[str] = ALLOWED_IMPORTS) -> ast.Module:
    """Parse and statically vet feature source. Returns the AST on success."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SafetyViolation(f"generated code does not parse: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for mod in names:
                root = mod.split(".")[0]
                if root not in allowed_imports:
                    raise SafetyViolation(f"import of {mod!r} is not allowed in generated features")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith)):
            raise SafetyViolation("async constructs are not allowed in generated features")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise SafetyViolation("global/nonlocal statements are not allowed in generated features")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise SafetyViolation(f"use of {node.id!r} is not allowed in generated features")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise SafetyViolation("dunder attribute access is not allowed in generated features")
        elif isinstance(node, (ast.Delete,)):
            raise SafetyViolation("del statements are not allowed in generated features")
    compile(tree, "<generated-feature>", "exec")
    return tree
