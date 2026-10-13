"""Real Python source formatting for extra-doc row708, never source execution.

AST equality is a structural check, not proof of runtime equivalence (line
numbers, source introspection and comment-based tools can observe changes).
"""
from __future__ import annotations

import ast
import difflib
import hashlib

MAX_BYTES = 25000
MAX_AST_NODES = 10000


class FormatterUnavailable(RuntimeError):
    pass


def _tree(source: str) -> str:
    try:
        tree = ast.parse(source, type_comments=True)
        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            raise ValueError("Python source exceeds AST node limit")
        return ast.dump(tree, include_attributes=False)
    except (SyntaxError, RecursionError, MemoryError) as exc:
        raise ValueError("Python source cannot be safely parsed") from exc


def format_python(source: str, line_length: int = 88) -> dict:
    if not isinstance(source, str):
        raise ValueError("source must be a string")
    try:
        encoded = source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("source contains invalid Unicode") from exc
    if len(encoded) > MAX_BYTES or "\x00" in source:
        raise ValueError("source exceeds byte limit or contains NUL")
    if type(line_length) is not int or not 40 <= line_length <= 200:
        raise ValueError("line_length must be an integer from 40 to 200")
    before_tree = _tree(source)
    try:
        import black
    except ImportError as exc:
        raise FormatterUnavailable("Black is not installed; install the code-formatting extra") from exc
    mode = black.Mode(line_length=line_length)
    try:
        formatted = black.format_str(source, mode=mode)
        if len(formatted.encode("utf-8")) > MAX_BYTES * 4:
            raise ValueError("formatter output exceeds byte limit")
        if _tree(formatted) != before_tree:
            raise ValueError("formatter changed the Python AST; result refused")
        second = black.format_str(formatted, mode=mode)
        if second != formatted:
            raise ValueError("formatter is not idempotent; result refused")
    except (black.InvalidInput, RecursionError, MemoryError) as exc:
        raise ValueError("formatter could not safely process Python source") from exc
    return {
        "feature_row": 708,
        "language": "python",
        "formatted_source": formatted,
        "changed": source != formatted,
        "diff": "".join(difflib.unified_diff(source.splitlines(True), formatted.splitlines(True),
                                           fromfile="before.py", tofile="after.py")),
        "before_sha256": hashlib.sha256(encoded).hexdigest(),
        "after_sha256": hashlib.sha256(formatted.encode("utf-8")).hexdigest(),
        "formatter": "black",
        "formatter_version": black.__version__,
        "line_length": line_length,
        "formatter_executed": True,
        "ast_equal": True,
        "second_pass_equal": True,
        "source_executed": False,
        "repository_mutated": False,
        "runtime_semantics_verified": False,
        "status": "python_source_formatted",
        "limits": ["Python only. Supplied text only; no file access or source execution.",
                   "AST equality and second-pass equality are checked, not runtime equivalence.",
                   "Line numbers, source introspection and comment-based tools may observe changes.",
                   "No repository write, merge, deployment or release is performed."],
    }
