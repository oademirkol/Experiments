#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "source.json"
DOCS_DIR = ROOT / "docs"
WIKI_DIR = ROOT / "wiki_output"


def load_source_data() -> dict:
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    default_data = {
        "title": "Daily Experiment",
        "status": "ready",
        "value": 42,
        "notes": "This file is replaced by your real source data later.",
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(default_data, f, indent=2)
    return default_data


def build_markdown(data: dict, timestamp: str) -> str:
    title = data.get("title", "Daily Experiment")
    status = data.get("status", "ready")
    value = data.get("value", 0)
    notes = data.get("notes", "")

    lines = [
        f"# {title}",
        "",
        f"Updated: {timestamp}",
        "",
        f"- Status: {status}",
        f"- Value: {value}",
        "",
        "## Notes",
        "",
        notes,
        "",
    ]
    return "\n".join(lines) + "\n"


def build_wiki_home(data: dict, timestamp: str, pages_url: str) -> str:
    title = data.get("title", "Daily Experiment")
    status = data.get("status", "ready")
    value = data.get("value", 0)
    notes = data.get("notes", "")

    lines = [
        f"# {title} Wiki",
        "",
        f"[Open GitHub Pages]({pages_url})",
        "",
        f"Updated: {timestamp}",
        "",
        "## Summary",
        "",
        f"- Status: {status}",
        f"- Value: {value}",
        "",
        "## Detailed notes",
        "",
        notes,
        "",
        "## Related pages",
        "",
        "- [Summary](Summary)",
        "",
    ]
    return "\n".join(lines) + "\n"


def build_wiki_summary(data: dict, timestamp: str, pages_url: str) -> str:
    title = data.get("title", "Daily Experiment")
    status = data.get("status", "ready")
    value = data.get("value", 0)

    lines = [
        "# Summary",
        "",
        f"[Back to GitHub Pages]({pages_url})",
        "",
        f"Updated: {timestamp}",
        "",
        f"- Repository page: {title}",
        f"- Current status: {status}",
        f"- Current value: {value}",
        "",
        "This page is intended for deeper notes and operational details.",
        "",
    ]
    return "\n".join(lines) + "\n"


def build_html(data: dict, timestamp: str, markdown_text: str) -> str:
    title = escape(data.get("title", "Daily Experiment"))
    status = escape(str(data.get("status", "ready")))
    value = escape(str(data.get("value", 0)))
    notes = escape(data.get("notes", ""))
    timestamp_escaped = escape(timestamp)

    content = "\n".join(
        [
            "<h1>" + title + "</h1>",
            "<p><strong>Updated:</strong> " + timestamp_escaped + "</p>",
            "<ul>",
            "<li><strong>Status:</strong> " + status + "</li>",
            "<li><strong>Value:</strong> " + value + "</li>",
            "</ul>",
            "<h2>Notes</h2>",
            "<p>" + notes.replace("\n", "<br>") + "</p>",
        ]
    )

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #222; }}
    h1, h2 {{ color: #0f172a; }}
    code {{ background: #f1f5f9; padding: 0.1rem 0.25rem; border-radius: 0.25rem; }}
    ul {{ line-height: 1.6; }}
  </style>
</head>
<body>
  {content}
</body>
</html>
"""


def main() -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data = load_source_data()
    markdown_text = build_markdown(data, timestamp)
    html_text = build_html(data, timestamp, markdown_text)

    pages_url = os.environ.get("GITHUB_PAGES_URL", "https://example.github.io/repo")
    wiki_home = build_wiki_home(data, timestamp, pages_url)
    wiki_summary = build_wiki_summary(data, timestamp, pages_url)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.md").write_text(markdown_text, encoding="utf-8")
    (DOCS_DIR / "index.html").write_text(html_text, encoding="utf-8")

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    (WIKI_DIR / "Home.md").write_text(wiki_home, encoding="utf-8")
    (WIKI_DIR / "Summary.md").write_text(wiki_summary, encoding="utf-8")

    print(f"Generated docs for {timestamp}")


if __name__ == "__main__":
    main()
