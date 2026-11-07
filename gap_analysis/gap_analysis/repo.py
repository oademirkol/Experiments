"""Clone or update the target GitHub repository using GH_PAT."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import git


def checkout_repo(cfg: Dict[str, Any]) -> Path:
    """Return the absolute path to the checked-out repo root.

    Set GH_PAT=LOCAL and add 'local_path' to config to skip cloning.
    """
    gh_pat = os.environ.get("GH_PAT", "")
    gh_cfg = cfg["github"]
    owner = gh_cfg["owner"]
    repo = gh_cfg["repo"]
    branch = gh_cfg["branch"]

    if gh_pat == "LOCAL":
        local_path = cfg.get("local_path")
        if not local_path:
            raise ValueError(
                "GH_PAT=LOCAL requires a 'local_path' key in config.yaml "
                "pointing to the local repository clone."
            )
        resolved = Path(local_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"local_path does not exist: {resolved}")
        return resolved

    if not gh_pat:
        raise EnvironmentError(
            "Environment variable GH_PAT is not set. "
            "Export your GitHub PAT or set GH_PAT=LOCAL for offline mode."
        )

    checkout_dir = Path(cfg.get("checkout_dir", f"_repo_cache/{repo}"))
    # Embed PAT in URL; never logged or written to disk beyond the git credential store
    remote_url = f"https://{gh_pat}@github.com/{owner}/{repo}.git"

    if checkout_dir.exists() and (checkout_dir / ".git").exists():
        repo_obj = git.Repo(checkout_dir)
        repo_obj.remotes.origin.fetch()
        repo_obj.git.reset("--hard", f"origin/{branch}")
    else:
        checkout_dir.parent.mkdir(parents=True, exist_ok=True)
        git.Repo.clone_from(remote_url, checkout_dir, branch=branch, depth=1)

    return checkout_dir.resolve()
