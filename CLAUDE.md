# CLAUDE.md — Lucid Project Context

> This file is auto-loaded by Claude Code at the start of every session.
> It is the single source of truth for project context.
> **Do not open other files until you need to work on them specifically.**
> Each file entry below says exactly when to open it.

---

## What Lucid Is

Lucid is an AI-powered documentation generator. You give it a GitHub repo URL, it clones it, analyzes the Python file structure using pure AST (no LLM), then makes 3–4 LLM synthesis calls and outputs **one self-contained HTML page per repo** — a visual, progressive explainer that a non-coder can open and understand in 10–15 minutes. It runs via a terminal CLI or a web UI served at `localhost:8000`.

It was built as Phase 1 of Aayush's decade doctrine — the first project in a 10-year arc toward Staff/Principal Document Engineer. The brief philosophy: ship a janky V1 and spend months fixing it in public.

**Current state (Day 08):** Phase 3a–3e shipped + HTML Intelligence Engine live. The full pipeline is end-to-end: clone → analyze → outline → 3 JSON calls → 1 HTML design call → iframe result in the browser. 4 LLM calls total per repo (~30 seconds). The web UI is fully wired: paste a GitHub URL, watch phase steps tick off, see the custom-designed page in an iframe. The pipeline no longer uses a fixed template — the 4th LLM call designs the entire HTML page from scratch to match each repo's personality.

---

## The Vision

> **Convert any GitHub repo into a Stripe-level documentation suite, automatically.**

Stripe's documentation is the gold standard. It is built on the Diataxis framework — four distinct doc types, each serving a different user mode:

| Type | User mode | What it answers |
|---|---|---|
| **Tutorial** | Learning | "Help me get started" — step-by-step, narrative, by doing |
| **How-to** | Task | "Help me do X" — problem-focused, assumes knowledge |
| **Reference** | Lookup | "What is X exactly?" — cold facts, precise, no fluff |
| **Explanation** | Understanding | "Why does X work this way?" — architecture, big picture |

Most doc generators produce one type badly. Lucid's goal is to produce all four cleanly for any repo. The axis is not *who the user is* — it's *what mode they're in right now*.

**What makes this novel:** Nobody generates all four Diataxis types for an arbitrary repo. Sphinx and JSDoc give you reference only. readme-ai gives you tutorial only. Lucid's gap to own is the full suite.

**Honest scope:** Stripe-level in *structure and navigation*. The depth Stripe gets from knowing their users' failure patterns cannot be automated. Human review is the layer on top.

---

## The Output — One HTML Page Per Repo

The deliverable is `output/<repo>/index.html` — a single, self-contained HTML page designed from scratch for each repo.

**No fixed template.** The HTML Intelligence Engine (4th LLM call) receives all structured content and designs the page from zero — choosing its own color palette, typography, layout, and visual voice to match the repo's personality. `learn/index.html` is now a quality reference and visual inspiration, not a CSS source that gets loaded at runtime.

**The persona:** The LinkedIn explorer. Curious, sharp, not an engineer. Sees a repo trending on social and wants to understand it. Works in marketing, product, ops, or founding.

**Vocabulary rule:** Explain like you're talking to a smart person at a dinner party who works in marketing. No unexplained jargon. If a technical term is unavoidable, define it in the same breath.

**Banned phrases (enforced in every Phase 3 prompt):**
- "This module provides a framework for…"
- "This repository…" or "This repo…"
- "A tool that allows users to…"
- "This file…" or "This module…"

---

### The 5 Sections — in build priority order

**1 — Pitch + Flow (THE MAGIC)**
The moment the explorer says "oh, I get it." Gets the strongest model (one call per repo).
- **One sentence:** `"You [give it X]. It [does Y]. You get [Z]."` Concrete nouns, max ~30 words.
- **Flow diagram:** 4–5 boxes with arrows. Each box ≤ 4 words. `[input] → [verb] → [verb] → [output]`.

**2 — Key Facts**
Small grid of `.status-card` cards. Plain-language: what problem it solves, language + why it matters, size/maturity, who it's for.

**3 — The Piece Map**
Not every file — every meaningful role. Group trivial files. A 40-file repo → 6–10 cards, not 40. Each card: plain name, one-line dinner-party role, one-line "why you'd care."

**4 — How It Moves**
One concrete trace from input to output. Reuses `.flow-diagram` / `.flow-node`. Plain labels, not function signatures.

**5 — The Honest Read**
What's clearly designed well, what's confusing, honest verdict on "can a non-expert follow this?"

---

### Progressive Depth — three layers in one HTML

- **Layer 1 (always visible):** Sections 1–3. Complete on its own.
- **Layer 2 (`<details open>`):** How It Moves, Honest Read, Architecture diagram.
- **Layer 3 (`<details>` closed):** The `deep` field under each piece card.

Implemented via native `<details>/<summary>` — zero JS.

---

## Project Map

Every file. Read the "open when" line to decide if you need it.

---

### Root Level

**`CLAUDE.md`** ← you are here

---

**`cli.py`**
Terminal entry point. `sys.argv[1]` = GitHub URL, `sys.argv[2]` = audience (optional, vestigial for HTML output — persona is hardcoded as LinkedIn explorer). Calls `pipeline.run()` and prints progress via an `on_progress` closure. Recognizes new SSE events: `outlining`, `html_pitch`, `html_pieces`, `html_honest`, `html_assembling`, `html_done`, `html_warn`, `html_error`. Prints the `open output/…/index.html` path after a successful run.

→ Open when: adding CLI flags, debugging terminal runs, updating progress messages.

---

**`server.py`**
FastAPI backend. Routes: `POST /generate`, `GET /events/{job_id}` (SSE), `GET /html?repo=<name>` (serves `output/<name>/index.html` with path-traversal guard), `GET /repos` (lists repo names that have a generated `index.html`). The old `/files` and `/doc` markdown routes are gone. The web UI is served from `web/index.html`.

→ Open when: adding API routes, debugging SSE events.

---

**`requirements.txt`**
Six dependencies: `anthropic`, `openai`, `fastapi`, `uvicorn[standard]`, `python-dotenv`, `pathspec`.

→ Open when: adding a new provider SDK or dependency.

---

**`.env.example`**
Template for all three providers + the new `LUCID_PITCH_MODEL` var. Live `.env` is gitignored.

Active config: `LUCID_PROVIDER=openai`, `LUCID_MODEL=gpt-5.4-nano`, `LUCID_PITCH_MODEL=gpt-5.4-mini`.

→ Open when: switching providers/models or onboarding a new machine.

---

### `lucid/` Package — The Core Engine

The package is now **seven files**. Call chain: `pipeline.py` → `analyze.py` + `code_outline.py` + `prompts.py` + `llm.py` + `html_render.py` ← `config.py`.

---

**`lucid/config.py`**
Loads `.env`, validates provider/audience, resolves API key. Exports: `PROVIDER`, `MODEL`, `PITCH_MODEL`, `AUDIENCE`, `API_KEY`. `PITCH_MODEL` defaults to `MODEL` if `LUCID_PITCH_MODEL` is not set.

→ Open when: adding a new provider, changing config loading.

---

**`lucid/llm.py`** — **The provider swap lives here**
Single public function: `generate(system, user, *, model=None, json_mode=False, max_tokens=2048) -> str`. `model` overrides `config.MODEL` for that call. `json_mode=True` adds `response_format={"type":"json_object"}` on the OpenAI path; is a no-op on Anthropic. OpenAI path uses `max_completion_tokens` (not `max_tokens` — newer models require this). Anthropic path uses `max_tokens`.

To add a new provider: add `_call_X()` and one `elif` branch. Interface is `(system, user, model, json_mode, max_tokens) -> str`.

→ Open when: adding a new LLM provider, debugging LLM call failures.

---

**`lucid/prompts.py`** — **12 builders total: 4 Phase 2 (kept for reference) + 6 Phase 3 JSON + 2 HTML engine (active)**

Phase 2 builders (not called by pipeline, kept as quality benchmarks):
- `build_reference_prompt(audience)`, `build_reference_user_prompt(filepath, code, see_also)`
- `build_tutorial_prompt(audience)`, `build_tutorial_user_prompt(repo_name, file_tree, graph_summary, entry_points, core_files, full_docs)`

Phase 3 JSON builders (produce structured dicts, feed into the HTML engine):
- `build_pitch_flow_prompt()` / `build_pitch_flow_user_prompt(repo_name, file_tree, entry_points, core_files, outlines)` — `_LINKEDIN_PERSONA` + `_JSON_INSTRUCTION`, returns `{pitch, flow}`.
- `build_piece_map_prompt()` / `build_piece_map_user_prompt(repo_name, file_tree, graph_summary, outlines)` — returns `{key_facts, pieces}`.
- `build_honest_read_prompt()` / `build_honest_read_user_prompt(repo_name, file_tree, pieces_hint, outlines)` — returns `{how_it_moves, honest_read}`.

HTML Intelligence Engine (4th call — designs the page):
- `build_html_engine_prompt()` — instructs the LLM to invent a palette/typography/layout matching the repo's personality. No fixed template. Output must start with `<!DOCTYPE html>`.
- `build_html_engine_user_prompt(repo_name, pitch, pieces, honest, mermaid, file_tree)` — serializes all three JSON blobs + file tree + Mermaid as the design brief.

→ Open when: improving output quality, tweaking banned phrases, adding new section types.

---

**`lucid/code_outline.py`** — **New in Phase 3. Pure AST, no LLM.**
Single public function: `extract_outline(path: Path) -> str`. Returns a short plain-text outline of one Python file: module name, top-level docstring, public classes with bases + first docstring line, public methods (`.name(params) — docstring`), public functions. Skips private symbols (leading `_`) except `__init__`. Never raises — returns `(parse error: ...)` on syntax errors. Replaces the per-file LLM fan-out from Phase 2.

→ Open when: improving outline quality, debugging outline content, adding new symbol types (e.g. constants, type aliases).

---

**`lucid/html_render.py`** — **Fallback only as of Day 08.**
The original template-based assembler. Still used when the HTML Intelligence Engine call fails. Single public function: `assemble(dest, repo_name, pitch, pieces, honest, mermaid) -> None`. Reads CSS from `learn/index.html` at import time. Do not extend this — it's the safety net, not the primary path.

→ Open when: debugging the template fallback path.

---

**`lucid/pipeline.py`** — **Rewritten in Phase 3, HTML engine added Day 08.**
The `run()` function. Six phases:

1. **Preflight** — `_preflight_check()` pings the LLM before touching the output dir.
2. **Clone** — `git clone --depth 1`.
3. **Analyze** — `analyze_repo()` → `RepoGraph`. Falls back to `_empty_graph()` on AST failure.
4. **Outline** — `extract_outline()` on every file in `graph.ranking_paths()` order. No LLM, fast.
5. **3 JSON synthesis calls:**
   - `html_pitch` — Pitch + Flow using `config.PITCH_MODEL`. Falls back to `config.MODEL` if the strong model fails.
   - `html_pieces` — Piece Map + Key Facts using `config.MODEL`.
   - `html_honest` — Honest Read + How It Moves using `config.MODEL`.
6. **HTML Intelligence Engine** — `generate()` call using `config.PITCH_MODEL` with `max_tokens=10000`. Passes all three JSON blobs + file tree + Mermaid to `build_html_engine_prompt/user_prompt`. `_extract_html()` strips fences/preamble from the raw response. Writes the HTML directly. Falls back to `html_render.assemble()` on failure.

Helper `_call_json(system, user, *, model, max_tokens=4096)` wraps `generate()` + `_extract_json()` + one retry on JSON parse failure. `_extract_json()` strips ` ```json ` fences and finds the outermost `{…}` via brace counting. `_extract_html()` strips ` ```html ` fences and finds `<!DOCTYPE`/`<html` start.

SSE events emitted: `checking_provider`, `cloning`, `analyzing`, `analyze_error`, `outlining:N`, `html_pitch`, `html_pieces`, `html_honest`, `html_assembling`, `html_done:<rel-path>`, `html_warn:…`, `html_error:…`, `no_python_files`, `finished`.

→ Open when: adding new synthesis sections, debugging pipeline failures, changing SSE events.

---

**`lucid/analyze.py`** — **Pure AST, no LLM. Phase 3 added `ranking_paths()`.**
Builds a `RepoGraph`. Public methods: `see_also()` (Phase 2, used only by old prompts), `documented_set()`, `file_tree_text()`, `graph_summary_text()`, `mermaid_graph_text()`, `ranking_paths(repo_root) -> list[Path]` (new in Phase 3 — maps `ranking` rel strings to absolute paths for the outline phase).

→ Open when: debugging import graph analysis, changing file classification, adding graph features.

---

**`lucid/__init__.py`**
Empty. Don't touch.

---

### `learn/`

**`learn/index.html`** — **THE VISUAL TEMPLATE AND CSS SOURCE OF TRUTH**
The dark-theme project map page. `html_render.py` loads its `<style>` block at runtime. Every component class used in generated output (`formula-box`, `status-card`, `file-card`, `flow-node`, etc.) lives here. **Never duplicate the CSS — always read it from this file.**

→ Open when: checking component patterns, updating CSS variables, verifying visual consistency.

---

### `web/`

**`web/index.html`** — single-file frontend
Warm paper aesthetic. Three views: **Idle** (URL input + previous results), **Progress** (8 phase steps tick off as SSE events arrive), **Result** (full-screen iframe with the generated HTML + thin bar showing repo name and "Open in tab" link). No markdown viewer, no sidebar, no marked.js. Previous results calls `/repos` and loads directly into the iframe.

→ Open when: fixing frontend bugs, adding new SSE event handling.

---

### `docs/`

**`docs/models-2026.md`** — LLM model reference. Dated 2026-05-20 — verify pricing if more than a month old.

→ Open when: deciding which model to use, wiring a new provider.

**`docs/START.md`** — startup cheatsheet. Quick commands for every session.

→ Open when: you forgot the startup command.

**`docs/devlog.html`** — living build journal with color-coded finding cards.

→ Open when: writing a devlog entry.

**`docs/lucid-brief.html`** — original project brief with decade doctrine context.

→ Open when: re-reading the original vision.

---

### `handoff/`

Session notes written at the end of each work session. Always read the most recent one first.

**`handoff/2026-05-31-day08.md`** ← most recent
Day 08 session. Phase 3e + HTML Intelligence Engine shipped. Web UI fully wired: idle → phase-step progress → full-screen iframe result. Server: replaced `/files`+`/doc` with `/html?repo=` and `/repos`. `llm.py`: fixed `max_completion_tokens` for OpenAI (newer models reject `max_tokens`). `prompts.py`: +2 HTML engine builders (`build_html_engine_prompt`, `build_html_engine_user_prompt`). `pipeline.py`: 4th call now generates full HTML from scratch via the engine; `html_render.assemble()` demoted to fallback. First live run succeeded on `python-dotenv`.

**`handoff/2026-05-31-day07.md`**
Day 07 session. Phase 3a–3d shipped. HTML pivot live. Pipeline rewritten — 4 LLM calls, outputs `output/<repo>/index.html`. New files: `lucid/code_outline.py`, `lucid/html_render.py`. Updated: `llm.py`, `prompts.py` (+6 Phase 3 builders), `pipeline.py` (full rewrite), `analyze.py` (+`ranking_paths`), `config.py` (+`PITCH_MODEL`), `cli.py`.

**`handoff/2026-05-31-day06.md`**
Day 06 session. Output format pivot locked. Created `learn/index.html`. Updated CLAUDE.md with full spec. No code changed.

**`handoff/2026-05-23-day05.md`**
Day 05 session. First live Phase 2 run (21 docs from `python-dotenv`). Mermaid graph added to `_OVERVIEW.md`.

**`handoff/2026-05-20-day03.md`**
Day 03 session. Phase 2 implementation complete. Diataxis Reference + Tutorial prompts live.

**`handoff/2026-05-20.md`**
Day 02 session. Vision lock. Translation symptom root cause. Diataxis + Stripe connection.

**`handoff/2026-05-16.md`**
Day 01 session. Phase 1 build log. First run on python-dotenv.

→ Open when: resuming after a gap and need session history.

---

### `output/`

Generated output. Not committed to git. Phase 3 writes `output/<repo>/index.html`. Old Phase 1/2 runs in `output/click/`, `output/python-dotenv/`, `output/tqdm/` are stale `.md` files.

→ Open when: inspecting generated output, comparing quality.

---

## Model Situation

**Current active config (`.env`):**
```
LUCID_PROVIDER=openai
LUCID_MODEL=gpt-5.4-nano
LUCID_PITCH_MODEL=gpt-5.4-mini
```

**Dual-model strategy (live as of Phase 3):** Pitch + Flow and the HTML Intelligence Engine both run on `LUCID_PITCH_MODEL` (two calls per repo). The three JSON synthesis calls run on `LUCID_MODEL`. Cost difference is negligible; quality difference on the first impression is everything.

**Why not xAI:** `XAI_API_KEY` is scoped to image generation only. For chat completions, create a new key at console.x.ai.

**Why not Anthropic:** No credits on this account.

Full model landscape in `docs/models-2026.md` — dated 2026-05-20, verify pricing.

---

## Phase Roadmap

| Phase | Status | What it is |
|---|---|---|
| Phase 1 | ✅ Done | Pipeline skeleton — clone, analyze, generate, save. CLI + web UI. |
| Phase 2a | ✅ Done | Rewrite `prompts.py` — Diataxis Reference + Tutorial prompts |
| Phase 2b | ✅ Done | Fix synthesis pass — tiered budget, full docs |
| Phase 2c | ✅ Done | `analyze.py` `see_also()` + structured cross-link injection |
| Phase 2d | ✅ Done | Mermaid architecture diagram in `_OVERVIEW.md` |
| Phase 2 live test | 🟡 Partial | `python-dotenv` ✅ — `click` comparison + `rich` stress test pending |
| Phase 3a | ✅ Done | New prompt builders — Pitch+Flow, Piece Map, Honest Read |
| Phase 3b | ✅ Done | `llm.py` — `model=` / `json_mode=` / `max_tokens=` override params |
| Phase 3c | ✅ Done | `pipeline.py` — HTML synthesis path, `code_outline.py`, `html_render.py` |
| Phase 3d | ✅ Done | Progressive depth — Layer 2 + Layer 3 via native `<details>/<summary>` |
| Phase 3e | ✅ Done | Web UI — iframe result view, `/html?repo=` + `/repos` routes, phase-step progress |
| HTML Intelligence Engine | ✅ Done | 4th LLM call designs entire HTML from scratch — palette, fonts, layout per repo |
| **Phase 3 live test** | 🟡 **Partial** | **First run worked. Need: cross-repo comparison (click, rich), quality iteration on prompts** |
| Phase 4 | ⬜ Future | Diff-based incremental updates |
| Phase 5 | ⬜ Future | Run on a real open source project, submit a PR |
| Blog post | ⬜ Future | "I ran an AI doc generator on 20 repos. Here's what it understood and what it missed." |

---

## How to Resume

```bash
cd "Downloads/TWID /Lucid"
source .venv/bin/activate
uvicorn server:app --reload
# open http://localhost:8000
```

Terminal-only (faster, skips the web UI):
```bash
python cli.py https://github.com/theskumar/python-dotenv
open output/python-dotenv/index.html
```

---

## Key Principles to Keep in Mind

1. **Persona first, structure second.** Before writing any new prompt, ask: would the LinkedIn explorer understand this? No jargon. Dinner-party voice.

2. **The pitch sentence is the whole product.** If someone can't get it in 30 seconds, every other section is wasted. Pitch + Flow gets the stronger model. Don't iterate on piece maps until the pitch is nailed.

3. **The import graph is wired in.** `analyze.py` builds the full cross-reference map. `code_outline.py` extracts AST outlines. Both feed synthesis without any LLM per-file calls. This is the cheapness and speed advantage.

4. **Dual-model strategy is intentional.** Pitch + Flow = `LUCID_PITCH_MODEL`. Everything else = `LUCID_MODEL`. One stronger call per repo — negligible cost, big quality difference on first impression.

5. **No fixed template.** The HTML Intelligence Engine designs each page from scratch. `learn/index.html` is a quality reference and inspiration, not a CSS source. If a generated page looks off, tune `build_html_engine_prompt()` — the design brief, not a template.

6. **Build in public, but don't optimize for engagement.** Ship first, write one honest post, record one silent demo.
