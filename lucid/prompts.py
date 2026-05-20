"""Audience-aware prompt builders for Lucid — Diataxis Reference + Tutorial."""

import os
from pathlib import Path

AUDIENCE_INSTRUCTIONS: dict[str, str] = {
    "developer": (
        "Audience: software developers who will read and modify this code. "
        "Be precise and technical. Use exact function, class, and parameter names. "
        "Include type information and short code references where helpful. "
        "Assume the reader is fluent in Python."
    ),
    "manager": (
        "Audience: a technical manager who understands software concepts but "
        "does not read source code day-to-day. Explain what each component does "
        "and why it exists — in terms of behaviour, responsibilities, and data flow. "
        "Do NOT include code snippets, raw signatures, or line-level detail. "
        "Refer to components by plain-English role, not by exact symbol names."
    ),
    "non-technical": (
        "Audience: a non-technical client or leadership stakeholder. "
        "Use plain English only. Explain purpose and value, not mechanics. "
        "No code, no file paths, no function names, no jargon. "
        "If a technical concept is unavoidable, explain it with a one-sentence analogy. "
        "Focus on what the software accomplishes for its users."
    ),
    "end-user": (
        "Audience: a person who will USE this software, not build or maintain it. "
        "Be task-oriented: explain what the software lets them do and how to use it. "
        "Focus on capabilities, inputs, outputs, and practical steps. "
        "No code internals, no architecture. Plain, direct language."
    ),
}

_REFERENCE_PREAMBLE = (
    "You are writing Diataxis REFERENCE documentation for a single Python module. "
    "Reference docs are cold facts: precise, structured, lookup-oriented. "
    "Do NOT open with a generic paragraph. Do NOT start with "
    "'This module provides...', '## Overview', or any sentence beginning with "
    "'This module' or 'This file'. "
    "The very first line of your output must be a level-1 heading with the module name. "
    "Document only what you can directly observe in the code — do not invent "
    "behaviour, parameters, or return types. If something is ambiguous, note it briefly. "
    "Skip sections that have no content."
)

_REFERENCE_STRUCTURE = """\
Structure your output exactly as follows (no deviations):

# <module.name>
One sentence stating the specific purpose of this module. Do NOT begin with "This module".

## Public API
A markdown table with columns: Name | Signature | Description
List every public class, function, and constant. One row per item.
Omit this section only if the file exports nothing.

## Behaviour Notes
Bullet list of non-obvious behaviours, constraints, side effects, or raised exceptions.
Omit this section entirely if there is nothing non-obvious to say.

## See Also
For each cross-reference entry provided in the prompt, render exactly one line:
- [display_name](link) — role (kind)
where display_name is the stem of the filename, link is the value from link= in the data,
role is "imports" or "imported_by", kind is "entry", "core", or "internal".
Omit this section entirely if no cross-references are provided."""

_TUTORIAL_PREAMBLE = (
    "You are writing Diataxis TUTORIAL documentation — specifically an introductory "
    "overview that helps a reader understand an entire codebase and know where to start. "
    "Tutorials are narrative and goal-oriented. Write for someone who just cloned the "
    "repo and wants to understand what it does and how to use it. "
    "Do NOT start with 'This repository', 'This repo', or 'This project'. "
    "Cross-link aggressively to the per-file docs provided — every named module should "
    "become a markdown link using the link= value shown in the data."
)

_TUTORIAL_STRUCTURE = """\
Structure your output exactly as follows (no deviations):

# <repo-name>
One compelling sentence that answers: what problem does this solve? Do NOT start with "This".

## Get Started
Name the 1-2 entry points and tell the reader exactly what to run or call first.
Link each entry point using the link= value from the per-file data provided.
Example: [cli.py](./cli.md)

## Top Features
A narrative description of the 3-6 most important capabilities.
Each named module must become a link using the provided link= values.

## How the Pieces Fit
A short paragraph naming the core modules and how they relate to each other.
Link every named module using the provided link= values.

## Reference
Links to all per-file documentation, grouped by role.
Group order: Entry Points, then Core Modules, then Internal.
Format each line as: - [filename](link) — one-sentence role description"""


def build_reference_prompt(audience: str) -> str:
    audience = audience if audience in AUDIENCE_INSTRUCTIONS else "developer"
    return (
        f"{_REFERENCE_PREAMBLE}\n\n"
        f"{AUDIENCE_INSTRUCTIONS[audience]}\n\n"
        f"{_REFERENCE_STRUCTURE}"
    )


def build_reference_user_prompt(
    filepath: str,
    code: str,
    see_also: list[dict],
) -> str:
    from_parent = str(Path(filepath).parent)

    see_also_block = ""
    if see_also:
        lines = []
        for item in see_also:
            rel = item["rel"]
            display = Path(rel).stem
            role = item["role"]
            kind = item["kind"]
            to_md = str(Path(rel).with_suffix(".md"))
            raw = os.path.relpath(to_md, from_parent).replace("\\", "/")
            link = raw if raw.startswith("..") else "./" + raw
            lines.append(f"  rel={rel}  display={display}  role={role}  kind={kind}  link={link}")
        see_also_block = "\n\nCross-references (render each as a See Also link):\n" + "\n".join(lines)

    return (
        f"Document this Python module: `{filepath}`"
        f"{see_also_block}\n\n"
        f"```python\n{code}\n```"
    )


def build_tutorial_prompt(audience: str) -> str:
    audience = audience if audience in AUDIENCE_INSTRUCTIONS else "developer"
    return (
        f"{_TUTORIAL_PREAMBLE}\n\n"
        f"{AUDIENCE_INSTRUCTIONS[audience]}\n\n"
        f"{_TUTORIAL_STRUCTURE}"
    )


def build_tutorial_user_prompt(
    repo_name: str,
    file_tree: str,
    graph_summary: str,
    entry_points: list[str],
    core_files: list[str],
    full_docs: list[tuple[str, str]],
) -> str:
    docs_block = "\n\n---\n\n".join(
        f"FILE: {rel}\nLINK: ./{Path(rel).with_suffix('.md').as_posix()}\n\n{content}"
        for rel, content in full_docs
    )
    return (
        f"Generate the overview document for: {repo_name}\n\n"
        f"Entry points: {', '.join(entry_points) or 'none identified'}\n"
        f"Core modules: {', '.join(core_files) or 'none'}\n\n"
        f"File tree:\n{file_tree}\n\n"
        f"Import graph:\n{graph_summary}\n\n"
        f"Per-file documentation (use these to cross-link — each starts with FILE: and LINK:):\n\n"
        f"{docs_block}\n\n"
        f"Now write the repository overview document for: {repo_name}"
    )
