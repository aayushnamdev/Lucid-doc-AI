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
        parts = msg.split(":", 4)
        match parts[0]:
            case "cloning":
                print(f"\n  Cloning {repo_url} ...")
            case "analyzing":
                print("  Analyzing import structure...")
            case "analyze_error":
                print(f"  Structure analysis skipped: {parts[1] if len(parts) > 1 else ''}")
            case "found":
                print(f"  Found {parts[1]} Python files\n")
            case "generating":
                i, total, path = parts[1], parts[2], parts[3]
                print(f"  [ ] [{i}/{total}] {path}", end="\r", flush=True)
            case "done":
                i, total, path = parts[1], parts[2], parts[3]
                print(f"  [x] [{i}/{total}] {path}          ")
            case "error":
                i, total, path = parts[1], parts[2], parts[3]
                err = parts[4] if len(parts) > 4 else ""
                print(f"  [!] [{i}/{total}] {path} — {err}")
            case "mapping":
                print("\n  Generating repository overview...")
            case "map_done":
                print("  Repository overview saved.")
            case "map_error":
                print(f"  Overview skipped: {parts[1] if len(parts) > 1 else ''}")
            case "no_python_files":
                print("  No Python files found.")
            case "finished":
                print("\n  All done.")

    try:
        saved = run(repo_url, output_dir, on_progress, audience=audience)
        if saved:
            print(f"  Generated {len(saved)} docs in output/")
    except Exception as e:
        print(f"\n  Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
