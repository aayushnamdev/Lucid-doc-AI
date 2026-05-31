"""Pure-AST code outline extractor — no LLM, replaces per-file fan-out."""
from __future__ import annotations

import ast
from pathlib import Path


def extract_outline(path: Path) -> str:
    """Return a short plain-text outline of a Python file.

    Format:
        module: <dotted.name>
        docstring: <first line of module docstring, or empty>
        class <Name>(<bases>) — <first docstring line>
        def <name>(<params>) — <first docstring line>

    Never raises — returns a parse-error line on syntax errors.
    Private symbols (leading _) are skipped unless they are methods
    of a public class.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        return f"module: {_module_from_path(path)}\n(parse error: {e})"
    except Exception as e:
        return f"module: {_module_from_path(path)}\n(read error: {e})"

    lines: list[str] = []
    lines.append(f"module: {_module_from_path(path)}")

    module_doc = ast.get_docstring(tree)
    if module_doc:
        lines.append(f"docstring: {_first_line(module_doc)}")

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            bases = ", ".join(_unparse_name(b) for b in node.bases)
            sig = f"{node.name}({bases})" if bases else node.name
            doc = _first_line(ast.get_docstring(node) or "")
            lines.append(f"class {sig}" + (f" — {doc}" if doc else ""))
            # Public methods of this class
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_") and item.name != "__init__":
                        continue
                    msig = f"  .{item.name}({_params(item)})"
                    mdoc = _first_line(ast.get_docstring(item) or "")
                    lines.append(msig + (f" — {mdoc}" if mdoc else ""))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            sig = f"{node.name}({_params(node)})"
            doc = _first_line(ast.get_docstring(node) or "")
            lines.append(f"def {sig}" + (f" — {doc}" if doc else ""))

    return "\n".join(lines)


def _module_from_path(path: Path) -> str:
    # Best-effort: convert path to dotted module name
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0].strip() if text.strip() else ""


def _params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = func.args
    names: list[str] = []
    # positional args
    for arg in args.args:
        if arg.arg != "self":
            names.append(arg.arg)
    if args.vararg:
        names.append(f"*{args.vararg.arg}")
    for arg in args.kwonlyargs:
        names.append(arg.arg)
    if args.kwarg:
        names.append(f"**{args.kwarg.arg}")
    # truncate long signatures
    if len(names) > 5:
        return ", ".join(names[:5]) + ", ..."
    return ", ".join(names)


def _unparse_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_unparse_name(node.value)}.{node.attr}"
    return "..."
