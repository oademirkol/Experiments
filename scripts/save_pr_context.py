#!/usr/bin/env python3
"""Saves PR metadata from environment variables to pr_context.json for the downstream workflow."""
from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    ctx = {
        # GitHub PR number (e.g. "42") — used to target the correct issue for comments
        "pr_number": os.environ["PR_NUMBER"],
        # PR head branch name (e.g. "feature/my-branch") — used to build raw.githubusercontent.com plot URLs
        "branch": os.environ["BRANCH"],
        # Unique ID of this workflow run — used to link back to the source run in the merged report
        "run_id": os.environ["RUN_ID"],
    }

    Path("pr_context.json").write_text(json.dumps(ctx, indent=2), encoding="utf-8")
    print(f"Saved PR context: PR #{ctx['pr_number']}, branch '{ctx['branch']}', run {ctx['run_id']}")


if __name__ == "__main__":
    main()
