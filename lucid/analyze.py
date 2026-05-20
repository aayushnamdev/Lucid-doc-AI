"""Import-graph analysis for a Python repo. No LLM calls — pure AST + pathlib."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

LITE_AUDIENCES = {"non-technical", "end-user"}

_ENTRY_POINT_NAMES = frozenset({
    "cli.py", "main.py", "__main__.py", "app.py", "server.py",
    "run.py", "manage.py", "setup.py", "wsgi.py", "asgi.py",
})


@dataclass
class FileNode:
    rel: str
    module: str
    imports: set[str] = field(default_factory=set)
    imported_by: set[str] = field(default_factory=set)
    external_imports: set[str] = field(default_factory=set)
    is_entry_point: bool = False
    is_core: bool = False
    parse_error: Optional[str] = None


@dataclass
class RepoGraph:
    nodes: dict[str, FileNode]
    entry_points: list[str]
    core_files: list[str]
    ranking: list[str]

    def see_also(self, rel: str, audience: str, max_items: int = 6) -> list[dict]:
        """Structured cross-link data for the per-file See Also section."""
        node = self.nodes.get(rel)
        if not node:
            return []
        doc_set = set(self.documented_set(audience))
        rank_index = {r: i for i, r in enumerate(self.ranking)}

        def _kind(r: str) -> str:
            n = self.nodes[r]
            if n.is_entry_point:
                return "entry"
            if n.is_core:
                return "core"
            return "internal"

        fallback_rank = len(self.ranking)
        imports_entries = sorted(
            node.imports & doc_set,
            key=lambda r: rank_index.get(r, fallback_rank),
        )
        imported_by_entries = sorted(
            node.imported_by & doc_set,
            key=lambda r: rank_index.get(r, fallback_rank),
        )

        result: list[dict] = []
        for r in imports_entries:
            result.append({
                "rel": r,
                "role": "imports",
                "kind": _kind(r),
                "rank": rank_index.get(r, fallback_rank),
            })
        for r in imported_by_entries:
            result.append({
                "rel": r,
                "role": "imported_by",
                "kind": _kind(r),
                "rank": rank_index.get(r, fallback_rank),
            })
        return result[:max_items]

    def relationship_context(self, rel: str) -> str:
        node = self.nodes.get(rel)
        if not node:
            return ""
        parts = []
        if node.is_entry_point:
            if node.imported_by:
                parts.append(
                    f"This file is an entry point — also imported by: "
                    f"{', '.join(sorted(node.imported_by))}."
                )
            else:
                parts.append(
                    "This file is an entry point (not imported by any other file in this repo)."
                )
        elif node.is_core:
            parts.append(
                f"This is a core module — imported by "
                f"{len(node.imported_by)} other file(s): "
                f"{', '.join(sorted(node.imported_by))}."
            )
        else:
            if node.imported_by:
                parts.append(f"Imported by: {', '.join(sorted(node.imported_by))}.")
            else:
                parts.append(
                    "This is a standalone internal module "
                    "(no other file in this repo imports it)."
                )
        if node.imports:
            parts.append(
                f"Depends on internal modules: {', '.join(sorted(node.imports))}."
            )
        if node.external_imports:
            parts.append(
                f"External dependencies used: "
                f"{', '.join(sorted(node.external_imports))}."
            )
        if node.parse_error:
            parts.append(
                f"Note: AST analysis failed ({node.parse_error}); "
                f"relationship data may be incomplete."
            )
        return "\n".join(parts)

    def documented_set(self, audience: str) -> list[str]:
        """Files that should get a per-file doc page for this audience."""
        if audience in LITE_AUDIENCES:
            important = set(self.entry_points) | set(self.core_files)
            return [r for r in self.ranking if r in important]
        return list(self.ranking)

    def file_tree_text(self) -> str:
        lines = []
        for rel in sorted(self.nodes.keys()):
            depth = rel.count("/")
            name = rel.split("/")[-1]
            prefix = "  " * depth
            node = self.nodes[rel]
            role = (
                " [entry point]" if node.is_entry_point
                else " [core]" if node.is_core
                else ""
            )
            lines.append(f"{prefix}{name}{role}")
        return "\n".join(lines)

    def graph_summary_text(self) -> str:
        lines = []
        for rel in self.ranking:
            node = self.nodes[rel]
            role = "entry" if node.is_entry_point else ("core" if node.is_core else "internal")
            imported_by = ", ".join(sorted(node.imported_by)) or "—"
            imports = ", ".join(sorted(node.imports)) or "—"
            lines.append(f"  {rel}  [{role}]")
            lines.append(f"    ← imported by: {imported_by}")
            lines.append(f"    → imports:     {imports}")
        lines.append("")
        lines.append(f"Entry points : {', '.join(self.entry_points) or 'none identified'}")
        lines.append(f"Core modules : {', '.join(self.core_files) or 'none'}")
        return "\n".join(lines)


# ── Module name helper ──────────────────────────────────────────────────────

def _module_name(repo_root: Path, file: Path) -> str:
    rel = file.relative_to(repo_root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_init_path(path_str: str) -> bool:
    return path_str.endswith("__init__.py")


# ── Import resolver ─────────────────────────────────────────────────────────

def _resolve_import(
    module: Optional[str],
    level: int,
    names: list[str],
    importer_module: str,
    module_index: dict[str, str],
) -> tuple[set[str], set[str]]:
    """Return (internal_rel_paths, external_top_level_names). Best-effort."""
    internal: set[str] = set()
    external: set[str] = set()

    if level == 0:
        if not module:
            return internal, external

        base_resolved = False

        if module in module_index:
            internal.add(module_index[module])
            base_resolved = True
        else:
            # Walk prefixes for dotted imports like `import a.b.c`
            parts = module.split(".")
            for i in range(len(parts) - 1, 0, -1):
                prefix = ".".join(parts[:i])
                if prefix in module_index:
                    internal.add(module_index[prefix])
                    base_resolved = True
                    break

        # Also check each imported name as a potential submodule
        for name in names:
            candidate = f"{module}.{name}"
            if candidate in module_index:
                internal.add(module_index[candidate])
                base_resolved = True

        if not base_resolved:
            external.add(module.split(".")[0])

    else:
        # Relative import
        if not importer_module:
            return internal, external

        importer_parts = importer_module.split(".")
        importer_path = module_index.get(importer_module, "")

        # Determine the anchor package
        if _is_init_path(importer_path):
            # __init__.py — the module IS the package
            package_parts = importer_parts[:]
        else:
            # Regular file — parent package = drop last component
            package_parts = importer_parts[:-1]

        # Climb level-1 additional packages
        climb = level - 1
        if climb > len(package_parts):
            return internal, external  # escapes repo

        if climb > 0:
            base_parts = package_parts[: len(package_parts) - climb]
        else:
            base_parts = package_parts[:]

        # Descend into module (e.g. `from ..pkg import x` → module="pkg")
        if module:
            base_parts = base_parts + module.split(".")

        base_dotted = ".".join(base_parts)

        # Dual resolution: try the base itself, then base.name for each name
        if base_dotted and base_dotted in module_index:
            internal.add(module_index[base_dotted])

        for name in names:
            candidate = f"{base_dotted}.{name}" if base_dotted else name
            if candidate in module_index:
                internal.add(module_index[candidate])

    return internal, external


# ── Main entry point ────────────────────────────────────────────────────────

def analyze_repo(repo_root: Path, files: list[Path]) -> RepoGraph:
    # Build module index: dotted_module → rel_posix_path
    module_index: dict[str, str] = {}
    rel_to_module: dict[str, str] = {}

    for f in files:
        mod = _module_name(repo_root, f)
        if not mod:
            continue
        rel = f.relative_to(repo_root).as_posix()
        module_index[mod] = rel
        rel_to_module[rel] = mod

    # Initialise nodes
    nodes: dict[str, FileNode] = {}
    for f in files:
        rel = f.relative_to(repo_root).as_posix()
        mod = rel_to_module.get(rel, "")
        nodes[rel] = FileNode(rel=rel, module=mod)

    # Parse each file and resolve imports
    for f in files:
        rel = f.relative_to(repo_root).as_posix()
        node = nodes[rel]
        importer_module = node.module

        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except SyntaxError as e:
            node.parse_error = str(e)
            continue
        except Exception as e:
            node.parse_error = str(e)
            continue

        for ast_node in ast.walk(tree):
            if isinstance(ast_node, ast.Import):
                for alias in ast_node.names:
                    intern, extern = _resolve_import(
                        module=alias.name,
                        level=0,
                        names=[],
                        importer_module=importer_module,
                        module_index=module_index,
                    )
                    node.imports.update(r for r in intern if r != rel)
                    node.external_imports.update(extern)

            elif isinstance(ast_node, ast.ImportFrom):
                names = [a.name for a in ast_node.names]
                intern, extern = _resolve_import(
                    module=ast_node.module,
                    level=ast_node.level,
                    names=names,
                    importer_module=importer_module,
                    module_index=module_index,
                )
                node.imports.update(r for r in intern if r != rel)
                node.external_imports.update(extern)

    # Build imported_by (inverse graph)
    for rel, node in nodes.items():
        for target_rel in node.imports:
            if target_rel in nodes:
                nodes[target_rel].imported_by.add(rel)

    # Compute in-degrees
    in_degrees = {rel: len(node.imported_by) for rel, node in nodes.items()}

    # 75th percentile threshold for "core"
    degree_values = sorted(in_degrees.values())
    if degree_values:
        p75_idx = max(0, int(len(degree_values) * 0.75) - 1)
        core_threshold = max(2, degree_values[p75_idx])
    else:
        core_threshold = 2

    # Classify each file
    entry_points: list[str] = []
    core_files: list[str] = []

    for rel, node in nodes.items():
        filename = rel.split("/")[-1]
        is_ep = in_degrees[rel] == 0 or filename in _ENTRY_POINT_NAMES
        is_core = (not is_ep) and in_degrees[rel] >= core_threshold
        node.is_entry_point = is_ep
        node.is_core = is_core
        if is_ep:
            entry_points.append(rel)
        elif is_core:
            core_files.append(rel)

    entry_points.sort()
    core_files.sort(key=lambda r: -in_degrees[r])

    # Ranking: high in-degree first, then total degree, then alphabetical
    def rank_key(rel: str) -> tuple:
        ind = in_degrees[rel]
        total = ind + len(nodes[rel].imports)
        return (-ind, -total, rel)

    ranking = sorted(nodes.keys(), key=rank_key)

    return RepoGraph(
        nodes=nodes,
        entry_points=entry_points,
        core_files=core_files,
        ranking=ranking,
    )
