"""Audience-aware prompt builders for Lucid — Diataxis Reference + Tutorial."""

import json
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


# ── Phase 3: LinkedIn-explorer HTML builders ───────────────────────────────

_LINKEDIN_PERSONA = """\
You are writing for the LinkedIn explorer: a smart non-coder who works in marketing,
product, ops, or founding. They saw this repo trending and want to understand it.
Curious, sharp — just not an engineer. Write like you're at a dinner party explaining
something interesting to a smart friend who works in marketing.
Plain English throughout. If a technical term is unavoidable, define it in the same breath.

BANNED OPENERS (never use these, even as part of a longer phrase):
- "This repository provides..."  /  "This repo..."
- "This module provides..."  /  "This file provides..."
- "A framework for..."
- "A tool that allows users to..."

If you catch yourself starting that way, stop and rewrite the sentence from scratch.
"""

_JSON_INSTRUCTION = """\
Return your answer as a single valid JSON object and NOTHING ELSE.
No markdown code fences. No explanation before or after the JSON.
The first character of your response must be '{' and the last must be '}'.
"""


def build_pitch_flow_prompt() -> str:
    return f"""\
{_LINKEDIN_PERSONA}
Your job: write the two-part "big idea" section for a repo explainer page.

PART 1 — The pitch sentence
One sentence. Max 30 words. Must match this exact pattern:
  "You [give it X]. It [does Y]. You get [Z]."
Use concrete nouns, not category words. "You paste a GitHub link" beats "Users provide a repository URL."
Never start with any banned opener.

PART 2 — The flow
A horizontal row of 4-5 boxes showing the journey from input to output.
Each box label must be 4 words or fewer — no full sentences, no function names.
Colors to use: green (input/start), yellow (processing), blue (AI/smart step), purple (output/result), red (error/warning).
Shape is rigid:
  [input] → [verb phrase] → [verb phrase] → [output]
First box: what the user provides. Last box: what they receive.

{_JSON_INSTRUCTION}
Return this exact JSON shape:
{{
  "pitch": "<one sentence, max 30 words, pattern: You X. It Y. You get Z.>",
  "flow": [
    {{"label": "<4 words max>", "color": "green"}},
    {{"label": "<4 words max>", "color": "yellow"}},
    {{"label": "<4 words max>", "color": "blue"}},
    {{"label": "<4 words max>", "color": "purple"}}
  ]
}}
4 to 5 flow items only. No extras."""


def build_pitch_flow_user_prompt(
    repo_name: str,
    file_tree: str,
    entry_points: list[str],
    core_files: list[str],
    outlines: list[tuple[str, str]],
) -> str:
    outlines_block = "\n\n".join(
        f"FILE: {rel}\n{outline}" for rel, outline in outlines
    )
    return (
        f"Write the pitch and flow for: {repo_name}\n\n"
        f"Entry points (what users interact with directly): {', '.join(entry_points) or 'none identified'}\n"
        f"Core files (most-imported, critical logic): {', '.join(core_files) or 'none'}\n\n"
        f"File tree:\n{file_tree}\n\n"
        f"Code outlines (module names, classes, functions — your source material):\n\n"
        f"{outlines_block}\n\n"
        f"Now write the pitch sentence and flow for {repo_name}. Return only JSON."
    )


def build_piece_map_prompt() -> str:
    return f"""\
{_LINKEDIN_PERSONA}
Your job: write two complementary sections for a repo explainer page.

SECTION A — Key Facts (a small grid of cards)
3 to 4 cards. Each has a short "value" and a plain-English "label".
Think of it like a quick-glance panel: what problem it solves, what language it's built in
(and why that matters in plain terms), how big/mature it is.
Don't use raw file counts as values — say "small weekend project" or "large production library."
Colors: green, blue, yellow, red.

SECTION B — The Piece Map (the main section)
Not every file — every meaningful ROLE. Group trivial files together.
A repo with 40 files gives you 6-10 cards, not 40.
For each card:
  - name: the file or folder that represents this role
  - badge: one of "working" | "partial" | "problem" | "untouched" (pick the most honest)
  - role: one line, dinner-party voice — "The thing that actually talks to the AI."
  - note: one line — "Why you'd open this file."
  - deep: (optional) 1-2 sentences of concrete detail for curious readers — actual function names,
    edge cases, what's tricky. Leave out if there's nothing interesting to say beyond role+note.

{_JSON_INSTRUCTION}
Return this exact JSON shape:
{{
  "key_facts": [
    {{"value": "<short>", "label": "<plain English>", "color": "green"}},
    ...
  ],
  "pieces": [
    {{
      "name": "<filename or folder>",
      "badge": "working",
      "role": "<one line, dinner-party voice>",
      "note": "<one line, why you'd care>",
      "deep": "<optional deeper detail>"
    }},
    ...
  ]
}}"""


def build_piece_map_user_prompt(
    repo_name: str,
    file_tree: str,
    graph_summary: str,
    outlines: list[tuple[str, str]],
) -> str:
    outlines_block = "\n\n".join(
        f"FILE: {rel}\n{outline}" for rel, outline in outlines
    )
    return (
        f"Write the key facts and piece map for: {repo_name}\n\n"
        f"File tree (use [entry point] and [core] annotations to identify important files):\n{file_tree}\n\n"
        f"Import graph (shows which files depend on which):\n{graph_summary}\n\n"
        f"Code outlines:\n\n{outlines_block}\n\n"
        f"Produce 3-4 key fact cards and 6-10 piece cards for {repo_name}. Return only JSON."
    )


def build_honest_read_prompt() -> str:
    return f"""\
{_LINKEDIN_PERSONA}
Your job: write two more sections for a repo explainer page.

SECTION A — How It Moves (one concrete trace)
Pick the single most representative path a piece of data takes through this system.
Follow it from what the user gives, through each major step, to what comes out.
Write a short intro sentence, then describe the journey as a sequence of nodes and arrows.
Keep labels plain — no function signatures, no file paths with slashes. Short phrases only.
Colors: green (start/input), yellow (intermediate), blue (smart/AI steps), purple (output).

SECTION B — The Honest Read (the section most generators skip)
Short, candid, fair. 2-3 strengths, 2-3 weaknesses, one verdict sentence.
Be specific — "the pipeline file is easy to follow" beats "code is well-structured."
Verdict should answer: "Can a non-expert actually understand this repo?"
Keep tone fair and constructive, not a teardown.

{_JSON_INSTRUCTION}
Return this exact JSON shape:
{{
  "how_it_moves": {{
    "intro": "<one sentence describing the trace>",
    "rows": [
      [
        {{"label": "<short phrase>", "color": "green"}},
        {{"label": "<short phrase>", "color": "yellow"}},
        {{"label": "<short phrase>", "color": "blue"}},
        {{"label": "<short phrase>", "color": "purple"}}
      ]
    ]
  }},
  "honest_read": {{
    "strengths": ["<specific strength>", "..."],
    "weaknesses": ["<specific weakness>", "..."],
    "verdict": "<one sentence answer to: can a non-expert follow this?>"
  }}
}}
The rows array contains one or more rows; each row is an array of node objects.
A node is either {{"label": "...", "color": "..."}} or {{"arrow": "→"}} for separators."""


def build_honest_read_user_prompt(
    repo_name: str,
    file_tree: str,
    pieces_hint: str,
    outlines: list[tuple[str, str]],
) -> str:
    outlines_block = "\n\n".join(
        f"FILE: {rel}\n{outline}" for rel, outline in outlines
    )
    return (
        f"Write the data-flow trace and honest read for: {repo_name}\n\n"
        f"File tree:\n{file_tree}\n\n"
        f"Piece map already written (for narrative consistency):\n{pieces_hint}\n\n"
        f"Code outlines:\n\n{outlines_block}\n\n"
        f"Produce the how-it-moves trace and honest read for {repo_name}. Return only JSON."
    )


# ── Phase 3e: HTML Intelligence Engine ────────────────────────────────────────

def build_html_engine_prompt() -> str:
    return """\
You are a front-end designer and HTML engineer with strong visual taste.

You receive structured documentation about a software project and generate ONE complete,
self-contained HTML page that explains it to a curious non-technical reader.

This is not template-filling. Before writing a single line of CSS, read the content and ask:
"What is this project's personality? What design vocabulary does it deserve?"

A testing library might earn a clinical, grid-based precision aesthetic.
An env-file loader might deserve something earthy, minimal, almost typographic.
A CLI framework might want bold colors, terminal energy, strong hierarchy.
Let the content tell you. Never default to a generic dark or light theme.

═══ HARD OUTPUT RULES ═══
• Your entire response must be the HTML document — nothing else.
• No markdown. No fences. No preamble. First character must be <.
• All CSS in a <style> block in <head>. No external CSS files.
• Link Google Fonts from https://fonts.googleapis.com — choose fonts that suit the project.
• You MAY include the Mermaid CDN for the architecture diagram only:
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
• No other external scripts or stylesheets.
• One scrollable page. All content readable without JavaScript (except Mermaid renders).

═══ DESIGN PRINCIPLES ═══
• Invent a color palette for this specific repo — primary, accent, background, text, muted.
• Choose typography intentionally: font family, size scale, weight, line-height, spacing.
• The pitch sentence must be the first thing the eye lands on above the fold.
• Use whitespace as a design element. Density is not richness.
• Progressive depth via native <details>/<summary>:
    - Medium depth sections (How it moves, Honest read): <details open>
    - Optional deep-dives: <details> (closed by default)

═══ VOICE RULES — enforce in every word of copy ═══
• Audience: smart non-engineer. Works in marketing, product, ops, or founding.
• Voice: dinner-party explanation. Not a manual.
• BANNED sentence starters:
    "This module provides..."  "This repository..."  "This repo..."
    "A tool that allows..."  "This file..."  "This project..."
• The pitch sentence MUST follow this exact pattern:
    "You [give it X]. It [does Y]. You get [Z]."
    Concrete nouns. Max ~30 words. No category words like "users" or "input".
• Every technical term must be defined in the same breath the first time it appears.

═══ REQUIRED SECTIONS ═══
Design all of these however you like — layout, order within a section, visual treatment are yours:
1. Hero — pitch sentence large and unmissable, one-line tagline, the flow diagram (boxes + arrows)
2. Key facts — quick-glance grid: problem solved, language, size/maturity, who it's for
3. The pieces — meaningful roles (6–10 cards for a 40-file repo, not 40 cards)
4. How it moves — one concrete data trace from input to output, shown as a visual flow
5. Honest read — what's well-designed, what's confusing, one-sentence verdict
6. Architecture — Mermaid diagram if one is provided and non-trivial

Flow diagrams and traces must be visual: styled boxes with arrows, not bullet lists."""


def build_html_engine_user_prompt(
    repo_name: str,
    pitch: dict,
    pieces: dict,
    honest: dict,
    mermaid: str,
    file_tree: str,
) -> str:
    return (
        f"Repo: {repo_name}\n\n"
        f"=== PITCH + FLOW ===\n{json.dumps(pitch, indent=2)}\n\n"
        f"=== KEY FACTS + PIECE MAP ===\n{json.dumps(pieces, indent=2)}\n\n"
        f"=== HOW IT MOVES + HONEST READ ===\n{json.dumps(honest, indent=2)}\n\n"
        f"=== FILE TREE (use as a complexity/scale signal) ===\n{file_tree}\n\n"
        f"=== ARCHITECTURE DIAGRAM (Mermaid — include if non-trivial) ===\n{mermaid}\n\n"
        f"Generate the complete HTML page for {repo_name}. "
        f"Start directly with <!DOCTYPE html> — no preamble, no fences, no explanation."
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
