#!/usr/bin/env python3
"""Lucid CLI — generate docs for a GitHub repo from the terminal."""

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python cli.py <github-url>")
        sys.exit(1)

    repo_url = sys.argv[1]
    audience = sys.argv[2] if len(sys.argv) > 2 else None
    output_dir = Path("output")

    from lucid.pipeline import run

    def on_progress(msg: str) -> None:
        parts = msg.split(":", 3)
        match parts[0]:
            case "cloning":
                print(f"\n  Cloning {repo_url} ...")
            case "analyzing":
                print("  Analyzing import structure...")
            case "analyze_error":
                print(f"  Structure analysis skipped: {parts[1] if len(parts) > 1 else ''}")
            case "outlining":
                print(f"  Reading code outlines ({parts[1] if len(parts) > 1 else '?'} files)...")
            case "html_pitch":
                print("  Synthesizing pitch + flow (strong model)...")
            case "html_pieces":
                print("  Synthesizing piece map + key facts...")
            case "html_honest":
                print("  Synthesizing honest read + data flow...")
            case "html_assembling":
                print("  Building HTML page...")
            case "html_done":
                path = parts[1] if len(parts) > 1 else ""
                print(f"  Page saved: output/{path}")
            case "html_warn":
                detail = ":".join(parts[1:]) if len(parts) > 1 else ""
                print(f"  ! {detail}")
            case "html_error":
                detail = ":".join(parts[1:]) if len(parts) > 1 else ""
                print(f"  ! HTML error: {detail}")
            case "no_python_files":
                print("  No Python files found.")
            case "finished":
                print("\n  Done.")

    html_path: str | None = None

    def on_progress_tracked(msg: str) -> None:
        nonlocal html_path
        if msg.startswith("html_done:"):
            html_path = msg[len("html_done:"):]
        on_progress(msg)

    try:
        saved = run(repo_url, output_dir, on_progress_tracked, audience=audience)
        if saved and html_path:
            print(f"\n  Open in browser: open output/{html_path}")
    except Exception as e:
        print(f"\n  Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
