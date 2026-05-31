"""Assembles the single-page HTML output from LLM JSON payloads.

CSS is loaded at runtime from learn/index.html (single source of truth).
Falls back to a minimal embedded stub if the template is missing.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

# ── CSS loading ─────────────────────────────────────────────────────────────

_CSS_CACHE: str | None = None
_LEARN_HTML = Path(__file__).parent.parent / "learn" / "index.html"

_FALLBACK_CSS = """
  :root {
    --bg:#0f0f13;--surface:#18181f;--surface2:#22222d;--border:#2e2e3d;
    --text:#e8e8f0;--muted:#7a7a94;--green:#4ade80;--green-dim:#1a3a25;
    --yellow:#fbbf24;--yellow-dim:#3a2e10;--red:#f87171;--red-dim:#3a1f1f;
    --blue:#60a5fa;--blue-dim:#1a2a3a;--purple:#a78bfa;--purple-dim:#2a1f3a;
    --accent:#818cf8;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:16px;line-height:1.6}
  .page{max-width:860px;margin:0 auto;padding:48px 24px 120px}
  h1{font-size:2.2rem;font-weight:700;letter-spacing:-.03em;color:#fff}
  h2{font-size:1.25rem;font-weight:600;color:#fff;margin-bottom:16px}
  h3{font-size:.95rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px}
  p{color:var(--muted);line-height:1.7}
  strong{color:var(--text)}
  .section{margin-top:64px}
  .divider{height:1px;background:var(--border);margin:48px 0}
  .hero{text-align:center;padding:64px 0 32px}
  .hero-badge{display:inline-block;background:var(--purple-dim);color:var(--purple);border:1px solid #4a3a7a;border-radius:20px;padding:4px 14px;font-size:.8rem;font-weight:600;letter-spacing:.05em;margin-bottom:20px}
  .hero h1{margin-bottom:16px}
  .big-idea{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:32px;text-align:center;margin-top:40px}
  .big-idea .formula{display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;margin:24px 0 0}
  .formula-box{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 20px;font-size:.9rem;color:var(--text);white-space:nowrap}
  .formula-arrow{color:var(--muted);font-size:1.2rem}
  .status-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}
  .status-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px;text-align:center}
  .status-number{font-size:2.5rem;font-weight:700;line-height:1;margin-bottom:6px}
  .status-label{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
  .file-grid{display:flex;flex-direction:column;gap:12px}
  .file-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px 24px;display:grid;grid-template-columns:1fr auto;gap:8px 16px;align-items:start}
  .file-name{font-family:'JetBrains Mono','Fira Code',monospace;font-size:.85rem;color:var(--accent);font-weight:600}
  .file-badge{font-size:.72rem;font-weight:700;letter-spacing:.06em;padding:3px 10px;border-radius:20px;white-space:nowrap}
  .badge-working{background:var(--green-dim);color:var(--green);border:1px solid var(--green)}
  .badge-partial{background:var(--yellow-dim);color:var(--yellow);border:1px solid var(--yellow)}
  .badge-problem{background:var(--red-dim);color:var(--red);border:1px solid var(--red)}
  .badge-untouched{background:var(--surface2);color:var(--muted);border:1px solid var(--border)}
  .file-role{font-size:.85rem;color:var(--muted);grid-column:1}
  .file-note{font-size:.82rem;color:var(--text);grid-column:1/-1;margin-top:4px;border-left:2px solid var(--border);padding-left:12px}
  .flow-diagram{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:32px;display:flex;flex-direction:column;gap:8px}
  .flow-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .flow-node{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:8px 16px;font-size:.85rem;color:var(--text);white-space:nowrap}
  .flow-node.green{border-color:var(--green);color:var(--green)}
  .flow-node.yellow{border-color:var(--yellow);color:var(--yellow)}
  .flow-node.blue{border-color:var(--blue);color:var(--blue)}
  .flow-node.purple{border-color:var(--purple);color:var(--purple)}
  .flow-node.red{border-color:var(--red);color:var(--red);border-style:dashed}
  .flow-arrow{color:var(--muted);font-size:1rem}
  .problem-card{background:var(--red-dim);border:1px solid #5a2a2a;border-radius:10px;padding:24px;margin-bottom:12px}
  .problem-card h2{color:var(--red);margin-bottom:10px}
  .problem-card p{color:#d0a0a0}
  .fix-card{background:var(--surface);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:10px;padding:20px 24px;margin-bottom:10px}
  .fix-card h2{color:var(--accent);font-size:.95rem;margin-bottom:8px}
  .fix-card p{font-size:.9rem}
  .callout{background:var(--blue-dim);border:1px solid #2a4060;border-left:3px solid var(--blue);border-radius:8px;padding:16px 20px;margin-top:16px;font-size:.9rem;color:#a0c4f0}
  .footer{text-align:center;color:var(--muted);font-size:.8rem;margin-top:80px;padding-top:24px;border-top:1px solid var(--border)}
  @media(max-width:600px){.status-grid{grid-template-columns:1fr}.big-idea .formula{flex-direction:column}}
"""

_DETAILS_CSS = """
  details > summary {
    cursor: pointer;
    color: var(--accent);
    list-style: none;
    font-size: 0.88rem;
    font-weight: 600;
    padding: 10px 0 4px;
    user-select: none;
  }
  details > summary::-webkit-details-marker { display: none; }
  details > summary::before { content: "▶  "; font-size: 0.7em; }
  details[open] > summary::before { content: "▼  "; }
  details > summary:hover { color: var(--text); }
  .deep-content {
    margin-top: 10px;
    font-size: 0.82rem;
    color: var(--muted);
    border-left: 2px solid var(--border);
    padding-left: 12px;
    line-height: 1.6;
  }
  .section-toggle > summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }
  .section-toggle > summary h2 {
    margin-bottom: 0;
    flex: 1;
  }
"""


def _load_css() -> str:
    global _CSS_CACHE
    if _CSS_CACHE is not None:
        return _CSS_CACHE
    try:
        text = _LEARN_HTML.read_text(encoding="utf-8")
        match = re.search(r"<style>(.*?)</style>", text, re.DOTALL)
        if match:
            css: str = match.group(1) + _DETAILS_CSS
            _CSS_CACHE = css
            return _CSS_CACHE
    except Exception:
        pass
    # Fallback — template missing or unreadable
    _CSS_CACHE = _FALLBACK_CSS + _DETAILS_CSS
    return _CSS_CACHE


# ── Section renderers ────────────────────────────────────────────────────────

def _e(text: str) -> str:
    """HTML-escape LLM-supplied strings."""
    return html.escape(str(text))


def _color_class(color: str) -> str:
    safe = {"green", "yellow", "blue", "purple", "red"}
    return color if color in safe else ""


def _render_hero(repo_name: str) -> str:
    name = _e(repo_name)
    return f"""
  <div class="hero">
    <div class="hero-badge">LUCID — REPO EXPLAINER</div>
    <h1>{name}</h1>
    <p>Plain-English explainer generated by Lucid. Read this to understand what the repo is, what it does, and whether you could follow it.</p>
  </div>"""


def _render_pitch(pitch: dict) -> str:
    sentence = _e(pitch.get("pitch", ""))
    flow_items = pitch.get("flow", [])

    boxes_html = ""
    for i, item in enumerate(flow_items):
        if not isinstance(item, dict):
            continue
        label = _e(item.get("label", ""))
        color = _color_class(item.get("color", ""))
        color_style = ""
        if color == "green":
            color_style = " style=\"border-color:var(--green);color:var(--green)\""
        elif color == "yellow":
            color_style = " style=\"border-color:var(--yellow);color:var(--yellow)\""
        elif color == "blue":
            color_style = " style=\"border-color:var(--blue);color:var(--blue)\""
        elif color == "purple":
            color_style = " style=\"border-color:var(--purple);color:var(--purple)\""
        elif color == "red":
            color_style = " style=\"border-color:var(--red);color:var(--red)\""

        if i > 0:
            boxes_html += '\n      <div class="formula-arrow">→</div>'
        boxes_html += f'\n      <div class="formula-box"{color_style}>{label}</div>'

    return f"""
  <div class="big-idea">
    <h3>What Is This Thing</h3>
    <p style="color:var(--text);font-size:1.1rem;font-weight:500;line-height:1.6;">{sentence}</p>
    <div class="formula">{boxes_html}
    </div>
  </div>"""


def _render_key_facts(key_facts: list) -> str:
    cards_html = ""
    color_map = {
        "green": "var(--green)",
        "yellow": "var(--yellow)",
        "blue": "var(--blue)",
        "purple": "var(--purple)",
        "red": "var(--red)",
    }
    for item in key_facts:
        if not isinstance(item, dict):
            continue
        value = _e(item.get("value", ""))
        label = _e(item.get("label", ""))
        color = item.get("color", "blue")
        css_color = color_map.get(color, "var(--blue)")
        cards_html += f"""
      <div class="status-card">
        <div class="status-number" style="color:{css_color};">{value}</div>
        <div class="status-label">{label}</div>
      </div>"""

    return f"""
  <div class="section">
    <h3>At a Glance</h3>
    <div class="status-grid">{cards_html}
    </div>
  </div>"""


def _render_piece_map(pieces: list) -> str:
    cards_html = ""
    valid_badges = {"working", "partial", "problem", "untouched"}
    for item in pieces:
        if not isinstance(item, dict):
            continue
        name = _e(item.get("name", ""))
        badge_raw = item.get("badge", "untouched")
        badge = badge_raw if badge_raw in valid_badges else "untouched"
        role = _e(item.get("role", ""))
        note = _e(item.get("note", ""))
        deep = item.get("deep", "")

        deep_html = ""
        if deep:
            deep_html = f"""
        <details>
          <summary>Show more</summary>
          <div class="deep-content">{_e(deep)}</div>
        </details>"""

        cards_html += f"""
      <div class="file-card">
        <span class="file-name">{name}</span>
        <span class="file-badge badge-{badge}">{badge.upper()}</span>
        <span class="file-role">{role}</span>
        <span class="file-note">{note}</span>{deep_html}
      </div>"""

    return f"""
  <div class="section">
    <h2>The Key Pieces</h2>
    <p style="margin-bottom:24px;">Every meaningful role — not every file. Grouped by what they collectively do.</p>
    <div class="file-grid">{cards_html}
    </div>
  </div>"""


def _render_how_it_moves(how_it_moves: dict) -> str:
    intro = _e(how_it_moves.get("intro", ""))
    rows = how_it_moves.get("rows", [])

    rows_html = ""
    for row in rows:
        if not isinstance(row, list):
            continue
        row_html = ""
        for item in row:
            if not isinstance(item, dict):
                continue
            if "arrow" in item:
                row_html += f'\n        <div class="flow-arrow">{_e(item["arrow"])}</div>'
            else:
                label = _e(item.get("label", ""))
                color = _color_class(item.get("color", ""))
                cls = f' class="flow-node{" " + color if color else ""}"'
                row_html += f"\n        <div{cls}>{label}</div>"
        rows_html += f"""
      <div class="flow-row">{row_html}
      </div>"""

    return f"""
  <details open class="section-toggle">
    <summary><h2>How It Moves — One Trace</h2></summary>
    <p style="margin-bottom:20px;">{intro}</p>
    <div class="flow-diagram">{rows_html}
    </div>
  </details>"""


def _render_honest_read(honest_read: dict) -> str:
    strengths = honest_read.get("strengths", [])
    weaknesses = honest_read.get("weaknesses", [])
    verdict = _e(honest_read.get("verdict", ""))

    strengths_html = ""
    for s in strengths:
        strengths_html += f"""
      <div class="fix-card">
        <p>{_e(s)}</p>
      </div>"""

    weaknesses_html = ""
    for w in weaknesses:
        weaknesses_html += f"""
      <div class="problem-card" style="padding:16px 20px;margin-bottom:8px;">
        <p>{_e(w)}</p>
      </div>"""

    return f"""
  <details open class="section-toggle">
    <summary><h2>The Honest Read</h2></summary>
    <h3 style="margin-top:16px;margin-bottom:12px;">What works</h3>
    {strengths_html}
    <h3 style="margin-top:20px;margin-bottom:12px;">What's confusing</h3>
    {weaknesses_html}
    <div class="callout" style="margin-top:16px;">
      <strong>Verdict:</strong> {verdict}
    </div>
  </details>"""


def _render_architecture(mermaid_text: str) -> str:
    if not mermaid_text.strip():
        return ""
    return f"""
  <details class="section-toggle">
    <summary><h2>Architecture Diagram</h2></summary>
    <p style="margin-bottom:20px;">Import graph — who depends on who. Green = entry points (where execution starts). Yellow = core modules (imported by most files).</p>
    <div class="mermaid">{mermaid_text}</div>
  </details>"""


# ── Public entry point ───────────────────────────────────────────────────────

def assemble(
    dest: Path,
    repo_name: str,
    pitch: dict,
    pieces: dict,
    honest: dict,
    mermaid: str,
) -> None:
    """Build and write the self-contained HTML page."""
    css = _load_css()

    key_facts = pieces.get("key_facts", [])
    piece_list = pieces.get("pieces", [])
    how_it_moves = honest.get("how_it_moves", {})
    honest_read = honest.get("honest_read", {})

    name_escaped = _e(repo_name)

    body = (
        _render_hero(repo_name)
        + _render_pitch(pitch)
        + _render_key_facts(key_facts)
        + '\n  <div class="divider"></div>'
        + _render_piece_map(piece_list)
        + '\n  <div class="divider"></div>'
        + _render_how_it_moves(how_it_moves)
        + '\n  <div class="divider"></div>'
        + _render_honest_read(honest_read)
        + '\n  <div class="divider"></div>'
        + _render_architecture(mermaid)
        + f"""
  <div class="footer">
    {name_escaped} — generated by <strong>Lucid</strong>
  </div>"""
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name_escaped} — Lucid</title>
<style>
{css}
</style>
</head>
<body>
<div class="page">
{body}
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true,theme:'dark'}});</script>
</body>
</html>"""

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page, encoding="utf-8")
