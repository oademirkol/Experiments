#!/usr/bin/env python3
"""Posts the hash report and plot as a new PR comment via GitHub REST API."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]  # "owner/repo"
    pr_number = os.environ["PR_NUMBER"]
    run_id = os.environ["GITHUB_RUN_ID"]
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    branch = os.environ["GITHUB_HEAD_REF"]

    report = Path("hash_report.md").read_text(encoding="utf-8")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}"
    plot_url = f"https://raw.githubusercontent.com/{repository}/{branch}/.github/plots/pr-{pr_number}.png"

    body = "\n".join([
        "## File Hash Report",
        "",
        f"**Branch:** `{branch}`  ",
        f"**Run:** [{run_id}]({run_url})  ",
        f"**Generated:** {timestamp}",
        "",
        "### File Extension Distribution",
        "",
        f"![File extension distribution]({plot_url})",
        "",
        "### File Hashes",
        "",
        report,
    ])

    payload = json.dumps({"body": body}).encode()
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
    print(f"Comment posted: {data['html_url']}")


if __name__ == "__main__":
    main()
