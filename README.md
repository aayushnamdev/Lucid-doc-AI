# Lucid

AI documentation generator — point it at a GitHub repo, get back a complete set of
markdown docs. Phase 1: janky but working. No RAG yet. That's the point.

## Quick start

```bash
# 1. Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# open .env and add your API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, or XAI_API_KEY)

# 3a. CLI
python cli.py https://github.com/username/repo

# 3b. Web UI (control panel)
uvicorn server:app --reload
# then open http://localhost:8000
```

## Model options

| Provider | Model ID | Input / Output (per 1M) | Notes |
|---|---|---|---|
| `anthropic` | `claude-haiku-4-5` | $1 / $5 | Default — cheap, coherent |
| `anthropic` | `claude-sonnet-4-6` | $3 / $15 | Higher quality |
| `openai` | `gpt-5.4-nano` | $0.20 / $1.25 | Cheapest OpenAI |
| `openai` | `gpt-5.4-mini` | $0.75 / $4.50 | Good OpenAI mid-tier |
| `xai` | `grok-4-1-fast` | $0.20 / $0.50 | Cheapest overall, 2M ctx |
| `xai` | `grok-4.3` | $1.25 / $2.50 | xAI flagship |

> Verify exact model IDs at your provider's docs before switching — they change.

Switch provider and model by editing `.env`:
```
LUCID_PROVIDER=xai
LUCID_MODEL=grok-4-1-fast
```

## Output

Generated docs appear in `output/<repo-name>/` mirroring the source tree.
Each Python file becomes a `.md` with the same relative path.

## Roadmap

- [x] Phase 1: clone → walk → generate → save + minimal web UI
- [ ] Phase 2: code validation layer (params / return types vs actual source)
- [ ] Phase 3: diff-based incremental updates
- [ ] Phase 4: RAG / vector store
- [ ] Phase 5: run on a real open source project, submit a PR

## Status

Phase 1 — shipping intentionally janky. V1 will hallucinate. That's the experiment.
