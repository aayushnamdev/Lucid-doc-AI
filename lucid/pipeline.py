import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import pathspec

from . import config
from .analyze import analyze_repo, FileNode, RepoGraph
from .llm import generate
from .prompts import (
    build_reference_prompt,
    build_reference_user_prompt,
    build_tutorial_prompt,
    build_tutorial_user_prompt,
)

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", ".mypy_cache", ".pytest_cache", ".tox",
}

_SYNTHESIS_TOKEN_BUDGET = 60_000
_CHARS_PER_TOKEN = 4


def _load_gitignore(repo_root: Path) -> pathspec.PathSpec:
    gi = repo_root / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _collect_python_files(repo_root: Path, spec: pathspec.PathSpec) -> list[Path]:
    files = []
    for path in sorted(repo_root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(repo_root)
        if spec.match_file(str(rel)):
            continue
        files.append(path)
    return files


def _extract_overview(markdown: str) -> str:
    """Return first prose line under ## Overview; fallback to first non-heading line."""
    lines = markdown.splitlines()
    in_overview = False
    for line in lines:
        if re.match(r"^##\s+Overview", line, re.IGNORECASE):
            in_overview = True
            continue
        if in_overview:
            if re.match(r"^##", line):
                break
            stripped = line.strip()
            if stripped:
                return stripped[:200]
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:200]
    return ""


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def _extract_reference_section(markdown: str) -> str:
    """Return everything before ## See Also, or the whole doc if no such section."""
    lines = markdown.splitlines()
    result = []
    for line in lines:
        if re.match(r"^##\s+See Also", line, re.IGNORECASE):
            break
        result.append(line)
    return "\n".join(result).strip() or markdown


def _trim_for_synthesis(
    full_docs: dict[str, str],
    ranking: list[str],
) -> tuple[list[tuple[str, str]], str]:
    """Return (selected_docs, tier) for the synthesis pass within token budget."""
    # Tier 1: full markdown
    all_full = [(rel, full_docs[rel]) for rel in ranking if rel in full_docs]
    if _estimate_tokens("".join(c for _, c in all_full)) <= _SYNTHESIS_TOKEN_BUDGET:
        return all_full, "full"

    # Tier 2: omit See Also sections to save tokens
    all_ref = [
        (rel, _extract_reference_section(full_docs[rel]))
        for rel in ranking if rel in full_docs
    ]
    if _estimate_tokens("".join(c for _, c in all_ref)) <= _SYNTHESIS_TOKEN_BUDGET:
        return all_ref, "reference"

    # Tier 3: 200-char snippets, walk ranking until budget exhausted
    selected: list[tuple[str, str]] = []
    used = 0
    for rel in ranking:
        if rel not in full_docs:
            continue
        snippet = _extract_overview(full_docs[rel])
        cost = _estimate_tokens(snippet)
        if used + cost > _SYNTHESIS_TOKEN_BUDGET and selected:
            break
        selected.append((rel, snippet))
        used += cost
    return selected, "snippet"


def _inject_architecture_section(md: str, mermaid: str) -> str:
    block = f"\n## Architecture\n\n```mermaid\n{mermaid}\n```\n"
    idx = md.find("\n## Reference")
    if idx != -1:
        return md[:idx] + block + md[idx:]
    return md.rstrip() + "\n\n## Architecture\n\n```mermaid\n" + mermaid + "\n```\n"


def _preflight_check() -> None:
    """Verify the configured LLM provider responds before touching the output directory."""
    try:
        generate("Reply with one word.", "ping")
    except Exception as e:
        raise RuntimeError(
            f"LLM provider check failed ({config.PROVIDER}/{config.MODEL}): {e}"
        ) from e


def _empty_graph(files: list[Path], repo_root: Path) -> RepoGraph:
    """Minimal graph with no edges — used when AST analysis fails."""
    nodes = {}
    for f in files:
        rel = f.relative_to(repo_root).as_posix()
        nodes[rel] = FileNode(rel=rel, module="", is_entry_point=True)
    ranking = sorted(nodes.keys())
    return RepoGraph(nodes=nodes, entry_points=ranking, core_files=[], ranking=ranking)


def run(
    repo_url: str,
    output_dir: Path,
    on_progress: Callable[[str], None] | None = None,
    audience: str | None = None,
) -> list[Path]:
    audience = (audience or config.AUDIENCE)
    if audience not in {"developer", "manager", "non-technical", "end-user"}:
        audience = "developer"

    def emit(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    emit("checking_provider")
    _preflight_check()

    emit("cloning")
    with tempfile.TemporaryDirectory() as tmpdir:
        clone_dest = Path(tmpdir) / "repo"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", repo_url, str(clone_dest)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr.strip()}")

        spec = _load_gitignore(clone_dest)
        files = _collect_python_files(clone_dest, spec)

        if not files:
            emit("no_python_files")
            return []

        # ── Phase 1: Analyze import graph ──────────────────────────────────
        emit("analyzing")
        try:
            graph = analyze_repo(clone_dest, files)
        except Exception as e:
            emit(f"analyze_error:{e}")
            graph = _empty_graph(files, clone_dest)

        # ── Phase 2: Determine which files to document ─────────────────────
        to_document = graph.documented_set(audience)
        emit(f"found:{len(to_document)}")

        repo_name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
        saved: list[Path] = []
        full_docs: dict[str, str] = {}

        system_prompt = build_reference_prompt(audience)
        total = len(to_document)

        def _process_file(args):
            i, rel_str = args
            src = clone_dest / rel_str
            emit(f"generating:{i}:{total}:{rel_str}")
            code = src.read_text(encoding="utf-8", errors="replace")
            see_also = graph.see_also(rel_str, audience)
            user_prompt = build_reference_user_prompt(rel_str, code, see_also)
            markdown = generate(system_prompt, user_prompt)
            rel_path = Path(rel_str)
            dest = output_dir / repo_name / rel_path.with_suffix(".md")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(markdown, encoding="utf-8")
            return rel_str, dest, markdown

        # ── Phase 3: Per-file documentation (concurrent) ──────────────────
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(_process_file, (i, rel_str)): rel_str
                for i, rel_str in enumerate(to_document, 1)
            }
            for i, future in enumerate(as_completed(futures), 1):
                rel_str = futures[future]
                try:
                    rel_str, dest, markdown = future.result()
                    saved.append(dest)
                    full_docs[rel_str] = markdown
                    emit(f"done:{i}:{total}:{rel_str}")
                except Exception as e:
                    emit(f"error:{i}:{total}:{rel_str}:{e}")

        # ── Phase 4: Repository overview (Diataxis Tutorial) ──────────────
        if saved:
            emit("mapping")
            try:
                selected, tier = _trim_for_synthesis(full_docs, graph.ranking)
                emit(f"synthesizing:{len(selected)}:{tier}")
                map_md = generate(
                    build_tutorial_prompt(audience),
                    build_tutorial_user_prompt(
                        repo_name=repo_name,
                        file_tree=graph.file_tree_text(),
                        graph_summary=graph.graph_summary_text(),
                        entry_points=graph.entry_points,
                        core_files=graph.core_files,
                        full_docs=selected,
                    ),
                )
                map_md = _inject_architecture_section(map_md, graph.mermaid_graph_text())
                map_dest = output_dir / repo_name / "_OVERVIEW.md"
                map_dest.parent.mkdir(parents=True, exist_ok=True)
                map_dest.write_text(map_md, encoding="utf-8")
                saved.append(map_dest)
                emit("map_done")
            except Exception as e:
                emit(f"map_error:{e}")

        emit("finished")
        return saved
