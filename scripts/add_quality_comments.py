#!/usr/bin/env python3
"""Adds review comments to modified files at line 1 during PR check-quality."""
from __future__ import annotations

import json
import os
import urllib.request


def get_pr_changed_files(repository: str, pr_number: str, token: str) -> list[str]:
    """Fetch list of changed files in the PR using GitHub REST API."""
    api_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
    req = urllib.request.Request(
        api_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as resp:
        files = json.loads(resp.read())
    return [f["filename"] for f in files]


def add_review_comment(
    repository: str,
    pr_number: str,
    token: str,
    filename: str,
    commit_id: str,
) -> str:
    """Add a review comment at line 1 of the specified file."""
    body = f"test checking {filename}"
    payload = json.dumps({
        "body": body,
        "commit_id": commit_id,
        "path": filename,
        "line": 1,
    }).encode()

    api_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/comments"
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
        result = json.loads(resp.read())
    return result["html_url"]


def main() -> None:
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    pr_number = os.environ["PR_NUMBER"]
    commit_id = os.environ["COMMIT_ID"]

    changed_files = get_pr_changed_files(repository, pr_number, token)
    print(f"Found {len(changed_files)} changed file(s)")

    for filename in changed_files:
        url = add_review_comment(repository, pr_number, token, filename, commit_id)
        print(f"  ✓ {filename} — {url}")


if __name__ == "__main__":
    main()
