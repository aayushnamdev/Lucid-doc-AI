# CLAUDE.md — Lucid Project Context

> This file is auto-loaded by Claude Code at the start of every session.
> It is the single source of truth for project context.
> **Do not open other files until you need to work on them specifically.**
> Each file entry below says exactly when to open it.

---

## What Lucid Is

Lucid is an AI-powered documentation generator. You give it a GitHub repo URL, it clones it, analyzes the Python file structure, sends each file to an LLM, and outputs structured Markdown documentation. It runs via a terminal CLI or a web UI served at `localhost:8000`.

It was built as Phase 1 of Aayush's decade doctrine — the first project in a 10-year arc toward Staff/Principal Document Engineer. The brief philosophy: ship a janky V1 and spend months fixing it in public.

**Current state:** Phase 1 skeleton is complete and working. The pipeline runs. The web UI works. The output is technically accurate but architecturally broken — it generates isolated per-file docs with no cross-linking, no narrative, no Diataxis structure. This is the known problem. Fixing it is the entire agenda for Phase 2+.

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

## The Known Problem — "Translation Symptom"

The current output reads like a translation, not documentation. Every `.md` file opens with `## Overview — This module provides...` There are zero cross-references. `decorators.md` never mentions it wraps `core.Command`. `_OVERVIEW.md` is a flat capabilities list.

**Root cause is architectural, not a model problem:**

| Cause | Location | Effect |
|---|---|---|
| Per-file isolation | `lucid/pipeline.py:127-142` | Each file generated in parallel with no knowledge of other files |
| Weak synthesis input | `lucid/pipeline.py:167` | Overview pass only sees 200-char snippets, never actual generated docs |
| One generic template | `lucid/prompts.py:33-85` | No Diataxis typing, no "works with" instruction, no See Also |

**Switching models makes it cheaper. It does not fix this.** The fix is three file changes:
1. `lucid/prompts.py` — rewrite to Diataxis-typed prompts
2. `lucid/pipeline.py:167` — feed the synthesis pass the actual generated `.md` files
3. Add a cross-linking pass that uses the import graph from `analyze.py` to inject "See also" sections

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

Current default: `LUCID_PROVIDER=anthropic`, `LUCID_MODEL=claude-haiku-4-5`
**Recommended switch** (zero code changes, ~9× cheaper): `LUCID_PROVIDER=xai`, `LUCID_MODEL=grok-4.1-fast`

Note: `.env.example` references `grok-4-1-fast` — some xAI model IDs were retired May 15 2026. Verify the current ID at docs.x.ai before using.

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

**`lucid/prompts.py`** — **The biggest lever for output quality**
Builds all prompts sent to the LLM. Four audience types (developer/manager/non-technical/end-user) × two prompt purposes (per-file doc, repository overview). Public functions: `build_system_prompt(audience)`, `build_user_prompt(filepath, code, relationships)`, `build_map_system_prompt(audience)`, `build_map_user_prompt(repo_name, tree, graph, summaries)`.

**This is the file that needs the most work.** The current per-file template generates one generic doc type regardless of audience — no Diataxis typing, no "works with" instruction, no See Also section. The template at `prompts.py:33-85` is what produces the "translation" output. Rewriting this to four Diataxis-typed prompts (Reference, Tutorial, How-to, Explanation) is the core Phase 2 work.

→ Open when: improving doc output quality, adding Diataxis doc types, fixing the translation symptom, changing what sections the LLM is asked to produce.

---

**`lucid/pipeline.py`** — **The orchestrator**
The main `run()` function. Four phases:

1. **Clone** (`pipeline.py:91-99`) — `git clone --depth 1` into a temp directory
2. **Analyze** (`pipeline.py:109-114`) — calls `analyze.py` to build the import graph
3. **Per-file generation** (`pipeline.py:127-155`) — `ThreadPoolExecutor(max_workers=8)` fires one LLM call per Python file concurrently. Each call gets the full file source + relationship context from the import graph. Saves each result as `output/{repo_name}/{filepath}.md`.
4. **Synthesis / overview** (`pipeline.py:157-177`) — one final LLM call that sees the file tree, import graph summary, and the first 200 chars of each generated doc. Writes `_OVERVIEW.md`.

**The synthesis pass at `pipeline.py:167` is broken by design.** It needs to be fed the actual generated `.md` file contents, not 200-char snippets. This is the architectural change required to enable cross-linking and real narrative.

→ Open when: changing the pipeline phases, fixing the synthesis pass, adding a new pass (e.g. cross-linking pass), debugging run failures.

---

**`lucid/analyze.py`** — **Pure AST, no LLM**
Builds a `RepoGraph` from the cloned repo using Python's `ast` module. No LLM involved — this is static analysis only. Classifies every file as entry point, core (imported by ≥75th percentile of files), or internal. Builds the full import graph (who imports who). Provides `relationship_context(rel)` which generates the "Imported by X, depends on Y" strings that get injected into per-file prompts.

**The import graph data here is already good.** The problem is that `prompts.py` only passes it as plain text context and doesn't instruct the LLM to turn it into "See also" links. The data is there — the instruction isn't.

→ Open when: debugging import graph analysis, changing how files are classified, adding new graph features (e.g. call graph, class hierarchy).

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

**`handoff/2026-05-20.md`** ← most recent
Day 02 session. Vision lock. Translation symptom root cause confirmed. Stripe reverse-engineering. Diataxis framework connection. Model research. The three-file fix identified. Day 03 checklist.

**`handoff/2026-05-16.md`**
Day 01 session. Phase 1 build log. What worked, what didn't, bugs fixed. First run on python-dotenv.

→ Open when: resuming after a gap and need session history.

---

### `output/`

Generated documentation from previous runs. Contains `output/click/` (25 docs from the click library — the run that confirmed the translation symptom). Not committed to git.

→ Open when: comparing old output to new output after a prompt/pipeline change.

---

## Model Situation

**Current default:** `claude-haiku-4-5` — $1.00 / $5.00 per 1M tokens, 200K context.

**Recommended immediate switch (zero code changes):**
```
LUCID_PROVIDER=xai
LUCID_MODEL=grok-4.1-fast
```
Cost: $0.20 / $0.50 per 1M. ~5–10× cheaper. Already wired in `llm.py`. 2M context window.

**Best long-term pick:** DeepSeek V4 Flash ($0.112 / $0.224) — requires adding OpenRouter or DeepSeek as a provider in `llm.py` (10 lines, OpenAI-compatible).

Full details in `docs/models-2026.md`.

---

## Phase Roadmap

| Phase | Status | What it is |
|---|---|---|
| Phase 1 | ✅ Done | Pipeline skeleton — clone, analyze, generate, save. CLI + web UI. |
| Phase 2a | 🔴 Next | Rewrite `prompts.py` — Diataxis-typed prompts (Reference + Tutorial at minimum) |
| Phase 2b | 🔴 Next | Fix synthesis pass — feed actual generated docs, not 200-char snippets |
| Phase 2c | 🔴 Next | Cross-linking pass — inject "See also" from import graph into each doc |
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

3. **The import graph is already there.** `analyze.py` builds the full cross-reference map. The problem is not data — it's that `prompts.py` doesn't instruct the LLM to turn that data into linked documentation.

4. **Don't swap models to fix quality.** Model swaps are a cost lever. Quality is a prompting and pipeline architecture problem.

5. **Build in public, but don't optimize for engagement.** Ship first, write one honest post, record one silent demo. Not a content calendar.
