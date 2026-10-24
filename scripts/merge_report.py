#!/usr/bin/env python3
"""Merges hash_report.md and the plot into a single report and posts it as a PR comment."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    ctx = json.loads(Path("pr_context.json").read_text(encoding="utf-8"))
    pr_number = ctx["pr_number"]
    branch = ctx["branch"]
    source_run_id = ctx["run_id"]

    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    merge_run_number = os.environ["MERGE_RUN_NUMBER"]
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")

    hash_report = Path("hash_report.md").read_text(encoding="utf-8")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source_run_url = f"{server_url}/{repository}/actions/runs/{source_run_id}"
    plot_url = f"https://raw.githubusercontent.com/{repository}/{branch}/.github/plots/pr-{pr_number}.png"

    merged = "\n".join([
        f"# Merged Hash Report — Run \#{merge_run_number}",
        "",
        f"**PR:** \#{pr_number}  ",
        f"**Branch:** `{branch}`  ",
        f"**Generated:** {timestamp}  ",
        f"**Source run:** [{source_run_id}]({source_run_url})  ",
        f"**Merge workflow run:** \#{merge_run_number}",
        "",
        "## File Extension Distribution",
        "",
        f"![File extension distribution]({plot_url})",
        "",
        "## File Hashes",
        "",
        hash_report,
    ])

    Path("merged_report.md").write_text(merged, encoding="utf-8")

    payload = json.dumps({"body": merged}).encode()
    api_url = f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments"

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    print(f"Merged report comment posted: {data['html_url']}")


if __name__ == "__main__":
    main()
