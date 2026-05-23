# CLAUDE.md — Lucid Project Context

> This file is auto-loaded by Claude Code at the start of every session.
> It is the single source of truth for project context.
> **Do not open other files until you need to work on them specifically.**
> Each file entry below says exactly when to open it.

---

## What Lucid Is

Lucid is an AI-powered documentation generator. You give it a GitHub repo URL, it clones it, analyzes the Python file structure, sends each file to an LLM, and outputs structured Markdown documentation. It runs via a terminal CLI or a web UI served at `localhost:8000`.

It was built as Phase 1 of Aayush's decade doctrine — the first project in a 10-year arc toward Staff/Principal Document Engineer. The brief philosophy: ship a janky V1 and spend months fixing it in public.

**Current state (Day 05):** Phase 2 is confirmed working end-to-end. First live run completed against `python-dotenv` (21 docs, OpenAI / gpt-4.1-nano). `_OVERVIEW.md` now includes a deterministic `## Architecture` Mermaid dependency graph injected after synthesis. Web UI Mermaid rendering is wired but needs browser validation next session.

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

Most doc generators produce one type badly. Lucid's goal is to produce all four cleanly for any repo. The axis is not *who the user is* — it's *what mode they're in right now*. A developer can be in all four modes depending on the moment.

**Honest scope:** Stripe-level in *structure and navigation*. The depth Stripe gets from knowing their users' failure patterns (10,000 developers trying the same thing wrong) cannot be automated. Human review is the layer on top. For most repos — which have only a README and scattered docstrings — Lucid getting to clean Diataxis output is already a genuine upgrade.

**What makes this novel:** Nobody generates all four Diataxis types for an arbitrary repo. Sphinx and JSDoc give you reference only. readme-ai gives you tutorial only. Lucid's gap to own is the full suite.

---

## The Translation Symptom — Fixed in Phase 2

The Phase 1 output read like a translation: every file opened with `## Overview — This module provides...`, zero cross-references, flat `_OVERVIEW.md`. Root cause was architectural.

**All three causes have been fixed:**

| Cause | Fix | Location |
|---|---|---|
| One generic template | Diataxis Reference + Tutorial prompts; "See Also" mandated | `lucid/prompts.py` (full rewrite) |
| Import graph as prose | `see_also()` returns structured link data; prompt injects it directly | `lucid/analyze.py` + `prompts.py` |
| Synthesis saw 200-char snippets | `_trim_for_synthesis()` — tiered budget, full docs first | `lucid/pipeline.py` |

**What the new output should look like:**
- Per-file docs open with `# module.name` (level-1 heading), then `## Public API` table, then `## See Also` with real links
- `_OVERVIEW.md` is a Tutorial — narrative, cross-linked, goal-oriented, not a flat list
- Files that import each other link to each other

**What's still not built:** How-to and Explanation doc types (Phase 3), test-extracted code examples, navigation index, per-file mini Mermaid diagrams (deferred).

---

## Project Map

Every file. Read the "open when" line to decide if you need it.

---

### Root Level

**`CLAUDE.md`** ← you are here
The master context file. Auto-loaded by Claude Code. Rewrite it when the project state changes significantly (after major feature additions, vision updates, architectural decisions).

---

**`cli.py`**
Terminal entry point. Accepts `--url` (GitHub repo URL), `--audience` (developer/manager/non-technical/end-user), and `--output` (output dir, defaults to `./output`). Calls `pipeline.run()` directly and prints progress messages to stdout. No server needed — pure terminal.

→ Open when: adding CLI flags, changing how progress is printed, debugging terminal runs.

---

**`server.py`**
FastAPI backend with four routes: `POST /generate` (kicks off a pipeline run in a background thread), `GET /events/{job_id}` (SSE stream of live progress events), `GET /files` (list all generated docs), `GET /doc` (read a specific doc by path). The web UI at `localhost:8000` is served from `web/index.html`. Runs pipeline in `ThreadPoolExecutor` so SSE stays responsive.

→ Open when: adding API routes, changing SSE event format, debugging web UI ↔ server communication.

---

**`requirements.txt`**
Six dependencies: `anthropic`, `openai`, `fastapi`, `uvicorn[standard]`, `python-dotenv`, `pathspec`. No vector DB, no RAG, no embeddings — Phase 2+ additions. The `openai` SDK handles both OpenAI and xAI (same SDK, different `base_url`).

→ Open when: adding a new provider SDK (e.g. `google-generativeai` for Gemini) or a new dependency.

---

**`.env.example`**
Template for all three currently-wired providers. Copy to `.env` and fill in keys. Live `.env` is gitignored — never commit it.

Active config: `LUCID_PROVIDER=openai`, `LUCID_MODEL=gpt-4.1-nano`. Do not change to xAI (image-only key) or Anthropic (no credits). See Model Situation section for full details.

→ Open when: switching providers/models or adding a new provider's key.

---

**`README.md`**
Public-facing project overview. Currently has a model comparison table and basic setup instructions.

→ Open when: updating public-facing documentation.

---

### `lucid/` Package — The Core Engine

This is where everything happens. The package is five files. They call each other in a clean chain: `pipeline.py` → `analyze.py` + `prompts.py` + `llm.py` ← `config.py`.

---

**`lucid/config.py`**
Loads `.env`, resolves and validates `LUCID_PROVIDER`, `LUCID_MODEL`, `LUCID_AUDIENCE`, and the matching API key. If anything is missing or invalid, it exits immediately with a clear message pointing to the fix. No silent failures. Exports four constants: `PROVIDER`, `MODEL`, `AUDIENCE`, `API_KEY`.

→ Open when: adding a new provider, adding a new audience type, changing how config is loaded.

---

**`lucid/llm.py`** — **The provider swap lives here**
Single public function: `generate(system: str, user: str) -> str`. Two internal branches: `_call_anthropic()` uses the Anthropic SDK directly. `_call_openai_compat()` handles OpenAI and xAI (xAI uses the same OpenAI SDK with `base_url="https://api.x.ai/v1"`). Both cap output at `max_tokens=2048`.

To add a new provider (e.g. Gemini, DeepSeek, OpenRouter): add one `_call_X()` function and one `elif provider == "X"` branch. The interface is fixed to `(system, user) -> str` — no tool use, no streaming, no multi-turn yet.

→ Open when: adding a new LLM provider, changing max tokens, debugging LLM call failures.

---

**`lucid/prompts.py`** — **Phase 2 complete rewrite**
Four public builders: `build_reference_prompt(audience)`, `build_reference_user_prompt(filepath, code, see_also)`, `build_tutorial_prompt(audience)`, `build_tutorial_user_prompt(repo_name, file_tree, graph_summary, entry_points, core_files, full_docs)`. `AUDIENCE_INSTRUCTIONS` is a tone modifier only — Diataxis structure is fixed regardless of audience.

Reference prompt: explicitly forbids `## Overview` and `This module provides...` openers. Mandates `# module.name` → `## Public API` table → `## Behaviour Notes` → `## See Also`.
Tutorial prompt: used for `_OVERVIEW.md` synthesis only. Mandates narrative hook → `## Get Started` → `## Top Features` → `## How the Pieces Fit` → `## Reference`.

→ Open when: improving doc output quality, adding How-to or Explanation doc types, tweaking prompt structure.

---

**`lucid/pipeline.py`** — **The orchestrator (Phase 2 rewrite)**
The main `run()` function. Four phases:

1. **Clone** — `git clone --depth 1` into a temp directory
2. **Analyze** — calls `analyze.py` to build the import graph
3. **Per-file generation** — `ThreadPoolExecutor(max_workers=8)`. Each file gets structured `see_also()` cross-link data injected into the prompt. Results stored in `full_docs` dict (full markdown, not snippets).
4. **Synthesis** — `_trim_for_synthesis()` applies a tiered token budget (full docs → reference sections → 200-char snippets) then calls `build_tutorial_prompt` + `build_tutorial_user_prompt` with actual generated content. Emits `synthesizing:{count}:{tier}` SSE event.

New helpers: `_estimate_tokens()`, `_extract_reference_section()`, `_trim_for_synthesis()`.

→ Open when: changing the pipeline phases, adding a new pass (e.g. How-to clustering), debugging run failures, adjusting the synthesis token budget.

---

**`lucid/analyze.py`** — **Pure AST, no LLM**
Builds a `RepoGraph` from the cloned repo using Python's `ast` module. Classifies every file as entry point, core (imported by ≥75th percentile of files), or internal. Two public methods for cross-linking:
- `relationship_context(rel)` — old method, returns English prose. Still present but no longer used by the pipeline.
- `see_also(rel, audience, max_items=6)` — Phase 2 method. Returns `list[dict]` with keys `rel`, `role`, `kind`, `rank`. Filtered through `documented_set(audience)`. Used by `pipeline.py` to inject structured link data into every per-file prompt.
- `mermaid_graph_text()` — Phase 2d method. Returns a `graph TD` Mermaid string for the full import graph. Walks `self.nodes` directly (not `see_also`) so it shows every file regardless of audience. Entry points styled green, core modules yellow. Used by `pipeline.py` to inject `## Architecture` into `_OVERVIEW.md`.

→ Open when: debugging import graph analysis, changing file classification logic, adding new graph features (call graph, class hierarchy).

---

**`lucid/__init__.py`**
Empty. Marks `lucid/` as a Python package. Don't touch.

---

### `web/`

**`web/index.html`** — single-file frontend
The entire web UI in one HTML file. Warm paper aesthetic, JetBrains Mono + Newsreader fonts. Features: GitHub URL input + audience selector, Generate button, live SSE progress checklist (file by file), split-pane doc viewer with marked.js markdown rendering, previous runs panel on idle screen. No build step, no framework, vanilla JS.

→ Open when: changing the UI layout, fixing frontend bugs, adding new UI features (audience selector changes, doc type selector for Diataxis).

---

### `docs/`

**`docs/models-2026.md`** — LLM model reference (created Day 02)
Full 2026 model landscape with pricing, context windows, and coding benchmarks. Top 3 picks for Lucid ranked by cheap + efficient. Cost reality check showing dollar cost per run across providers. Includes migration notes for adding new providers to `llm.py`. **Read this before choosing a model.** Dated 2026-05-20 — prices change, check sources if more than a month old.

→ Open when: deciding which model to use, wiring a new provider, comparing costs.

---

**`docs/START.md`** — startup cheatsheet
Quick commands for every session: activate venv, run server, run CLI, first-time setup. Human-readable. Does not contain project context.

→ Open when: you forgot the startup command.

---

**`docs/devlog.html`** — build journal
Living dev log with date entries and color-coded finding cards (bug/win/note/insight). Filter bar by type. This is the build-in-public artifact.

→ Open when: writing a new devlog entry.

---

**`docs/lucid-brief.html`** — project brief
Original project brief. Contains the full decade doctrine context, phase roadmap, build-in-public plan, multi-provider A/B blog post angle.

→ Open when: you need to re-read the original brief or share the project vision.

---

**`docs/the-learning-loop.html`** and **`docs/Decade-TWID-Journey.html`**
Career and learning context documents. Not directly related to Lucid's code.

→ Open when: grounding decisions in the broader career arc.

---

### `handoff/`

Session notes written at the end of each work session. Always read the most recent one first.

**`handoff/2026-05-23-day05.md`** ← most recent
Day 05 session. First live Phase 2 run on `python-dotenv` (21 docs). Mermaid dependency graph added: `analyze.py` got `mermaid_graph_text()`, `pipeline.py` got `_inject_architecture_section()`, `web/index.html` got Mermaid CDN + render hook. `_OVERVIEW.md` now has `## Architecture` with a role-styled `graph TD`. Web UI Mermaid rendering wired but browser validation pending.

**`handoff/2026-05-20-day03.md`**
Day 03 session. Phase 2 implementation complete. `analyze.py` + `prompts.py` + `pipeline.py` all rewritten. Diataxis Reference + Tutorial prompts live. Synthesis pass reads full generated docs. Note: handoff says model was switched to xAI — that turned out to be a dead end (xAI key is image-only, model IDs invalid). Active provider is now OpenAI / gpt-4.1-nano.

**`handoff/2026-05-20.md`**
Day 02 session. Vision lock. Translation symptom root cause confirmed. Stripe reverse-engineering. Diataxis framework connection. Model research. The three-file fix identified.

**`handoff/2026-05-16.md`**
Day 01 session. Phase 1 build log. What worked, what didn't, bugs fixed. First run on python-dotenv.

→ Open when: resuming after a gap and need session history.

---

### `output/`

Generated documentation from previous runs. Not committed to git.
- `output/click/` — Phase 1 output (May 16). The canonical "translation symptom" example. Use for before/after comparison.
- `output/python-dotenv/`, `output/tqdm/` — also Phase 1 output. Generated while xAI provider was broken — all runs failed silently, output was stale cached files.

The first clean Phase 2 output will overwrite these when run with OpenAI.

→ Open when: comparing Phase 1 vs Phase 2 output quality.

---

## Model Situation

**Current active provider:** `openai` / `gpt-4.1-nano`

```
LUCID_PROVIDER=openai
LUCID_MODEL=gpt-4.1-nano
```

This is the confirmed-working setup. gpt-4.1-nano follows the Diataxis formatting instructions correctly.

**Why not xAI:** The XAI_API_KEY in `.env` is scoped to image generation only (grok-imagine-image / grok-imagine-video). It has no access to chat completions. To use xAI, create a new API key at console.x.ai with Chat Completions enabled. Correct model name is `grok-4.3`.

**Why not Anthropic:** No credits on this account.

**Available OpenAI models if gpt-4.1-nano quality is insufficient:** `gpt-4.1-mini` (better, slightly more expensive), `gpt-4.1` (full model).

Full details in `docs/models-2026.md`.

---

## Phase Roadmap

| Phase | Status | What it is |
|---|---|---|
| Phase 1 | ✅ Done | Pipeline skeleton — clone, analyze, generate, save. CLI + web UI. |
| Phase 2a | ✅ Done | Rewrite `prompts.py` — Diataxis Reference + Tutorial prompts, See Also instruction |
| Phase 2b | ✅ Done | Fix synthesis pass — feeds full generated `.md` content (tiered budget) |
| Phase 2c | ✅ Done | `analyze.py` `see_also()` + structured cross-link injection into per-file prompt |
| Phase 2d | ✅ Done | Mermaid architecture diagram in `_OVERVIEW.md` — deterministic, role-styled `graph TD` |
| Phase 2 live test | 🟡 Partial | `python-dotenv` ✅ — `click` comparison + `rich` stress test still pending |
| Phase 3 | ⬜ Future | Code validation — compare generated param names against real AST |
| Phase 4 | ⬜ Future | Diff-based incremental updates |
| Phase 5 | ⬜ Future | Run on a real open source project, submit a PR |
| Blog post | ⬜ Future | "I ran an AI doc generator on 20 files. Here's what it understood and what it missed." |

---

## How to Resume

```bash
cd "Downloads/TWID /Lucid"
source .venv/bin/activate
uvicorn server:app --reload
# open http://localhost:8000
```

Or terminal-only:
```bash
python cli.py https://github.com/username/repo --audience developer
```

---

## Key Principles to Keep in Mind

1. **Diataxis first.** Before writing any new prompt, ask: which of the four doc types is this? Reference = cold facts. Tutorial = narrative flow. How-to = task orientation. Explanation = architecture reasoning.

2. **Stripe as the benchmark.** When in doubt about output quality, ask: would this pass as a Stripe docs page? If not, the prompt is the first place to look.

3. **The import graph is wired in.** `analyze.py` builds the full cross-reference map. Phase 2 wired it into `see_also()` and the per-file prompt injects it as structured link data. The LLM is now told exactly what to link and where.

4. **Don't swap models to fix quality.** Model swaps are a cost lever. Quality is a prompting and pipeline architecture problem.

5. **Build in public, but don't optimize for engagement.** Ship first, write one honest post, record one silent demo. Not a content calendar.
