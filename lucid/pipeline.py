import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import pathspec

from . import config
from . import html_render
from .analyze import analyze_repo, FileNode, RepoGraph
from .code_outline import extract_outline
from .llm import generate
from .prompts import (
    build_pitch_flow_prompt,
    build_pitch_flow_user_prompt,
    build_piece_map_prompt,
    build_piece_map_user_prompt,
    build_honest_read_prompt,
    build_honest_read_user_prompt,
    build_html_engine_prompt,
    build_html_engine_user_prompt,
)

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", ".mypy_cache", ".pytest_cache", ".tox",
}


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


def _preflight_check() -> None:
    try:
        generate("Reply with one word.", "ping")
    except Exception as e:
        raise RuntimeError(
            f"LLM provider check failed ({config.PROVIDER}/{config.MODEL}): {e}"
        ) from e


def _empty_graph(files: list[Path], repo_root: Path) -> RepoGraph:
    nodes = {}
    for f in files:
        rel = f.relative_to(repo_root).as_posix()
        nodes[rel] = FileNode(rel=rel, module="", is_entry_point=True)
    ranking = sorted(nodes.keys())
    return RepoGraph(nodes=nodes, entry_points=ranking, core_files=[], ranking=ranking)


def _extract_json(text: str) -> dict:
    """Strip fences and parse the outermost JSON object."""
    # Strip ```json fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    # Find outermost { … } via brace counting
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise json.JSONDecodeError("Unterminated JSON object", text, len(text))


def _extract_html(text: str) -> str:
    """Strip fences/preamble and return the HTML document."""
    text = text.strip()
    text = re.sub(r"^```(?:html)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    lower = text.lower()
    for marker in ("<!doctype", "<html"):
        idx = lower.find(marker)
        if idx >= 0:
            return text[idx:]
    return text


def _call_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
) -> dict:
    """Call the LLM and parse JSON. Retries once on parse failure."""
    current_user = user
    for attempt in (1, 2):
        raw = generate(system, current_user, model=model, json_mode=True,
                       max_tokens=max_tokens)
        try:
            return _extract_json(raw)
        except (json.JSONDecodeError, ValueError):
            if attempt == 2:
                raise
            current_user = (
                user + "\n\nYour previous response was not valid JSON. "
                "Return only a JSON object — no prose, no fences."
            )
    return {}  # unreachable


def run(
    repo_url: str,
    output_dir: Path,
    on_progress: Callable[[str], None] | None = None,
    audience: str | None = None,
) -> list[Path]:
    # audience kept for API compatibility but unused in HTML path
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

        repo_name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")

        # ── Phase 2: Extract code outlines (AST, no LLM) ──────────────────
        ranked_paths = graph.ranking_paths(clone_dest)
        emit(f"outlining:{len(ranked_paths)}")
        outlines: list[tuple[str, str]] = [
            (p.relative_to(clone_dest).as_posix(), extract_outline(p))
            for p in ranked_paths
        ]

        # ── Phase 3: Pitch + Flow (strong model) ──────────────────────────
        emit("html_pitch")
        try:
            pitch = _call_json(
                build_pitch_flow_prompt(),
                build_pitch_flow_user_prompt(
                    repo_name=repo_name,
                    file_tree=graph.file_tree_text(),
                    entry_points=graph.entry_points,
                    core_files=graph.core_files,
                    outlines=outlines,
                ),
                model=config.PITCH_MODEL,
            )
        except Exception as e:
            emit(f"html_warn:pitch_model_failed:{e} — retrying with default model")
            try:
                pitch = _call_json(
                    build_pitch_flow_prompt(),
                    build_pitch_flow_user_prompt(
                        repo_name=repo_name,
                        file_tree=graph.file_tree_text(),
                        entry_points=graph.entry_points,
                        core_files=graph.core_files,
                        outlines=outlines,
                    ),
                )
            except Exception as e2:
                emit(f"html_warn:pitch_unavailable:{e2}")
                pitch = {
                    "pitch": f"Explore {repo_name} — pitch generation failed.",
                    "flow": [{"label": repo_name, "color": "purple"}],
                }

        # ── Phase 4: Piece Map + Key Facts (nano) ─────────────────────────
        emit("html_pieces")
        try:
            pieces = _call_json(
                build_piece_map_prompt(),
                build_piece_map_user_prompt(
                    repo_name=repo_name,
                    file_tree=graph.file_tree_text(),
                    graph_summary=graph.graph_summary_text(),
                    outlines=outlines,
                ),
            )
        except Exception as e:
            emit(f"html_warn:pieces_unavailable:{e}")
            pieces = {"key_facts": [], "pieces": []}

        # ── Phase 5: Honest Read + How It Moves (nano) ────────────────────
        emit("html_honest")
        try:
            honest = _call_json(
                build_honest_read_prompt(),
                build_honest_read_user_prompt(
                    repo_name=repo_name,
                    file_tree=graph.file_tree_text(),
                    pieces_hint=json.dumps(pieces),
                    outlines=outlines,
                ),
            )
        except Exception as e:
            emit(f"html_warn:honest_unavailable:{e}")
            honest = {"how_it_moves": {"intro": "", "rows": []},
                      "honest_read": {"strengths": [], "weaknesses": [], "verdict": ""}}

        # ── Phase 6: HTML Intelligence Engine ─────────────────────────────
        emit("html_assembling")
        dest = output_dir / repo_name / "index.html"
        mermaid = graph.mermaid_graph_text()
        try:
            raw = generate(
                build_html_engine_prompt(),
                build_html_engine_user_prompt(
                    repo_name=repo_name,
                    pitch=pitch,
                    pieces=pieces,
                    honest=honest,
                    mermaid=mermaid,
                    file_tree=graph.file_tree_text(),
                ),
                model=config.PITCH_MODEL,
                max_tokens=10000,
            )
            html = _extract_html(raw)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(html, encoding="utf-8")
            rel_str = str(dest.relative_to(output_dir))
            emit(f"html_done:{rel_str}")
        except Exception as e:
            emit(f"html_warn:engine_failed — falling back to template: {e}")
            try:
                html_render.assemble(
                    dest=dest,
                    repo_name=repo_name,
                    pitch=pitch,
                    pieces=pieces,
                    honest=honest,
                    mermaid=mermaid,
                )
                rel_str = str(dest.relative_to(output_dir))
                emit(f"html_done:{rel_str}")
            except Exception as e2:
                emit(f"html_error:assemble:{e2}")
                emit("finished")
                return []

        emit("finished")
        return [dest]
