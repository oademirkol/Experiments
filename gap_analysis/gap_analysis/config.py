"""Load and validate config.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

_REQUIRED: Dict[str, list] = {
    "github": ["owner", "repo", "branch", "gap_spec_dir"],
    "output": ["base_dir"],
}


def load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not cfg:
        raise ValueError("Config file is empty.")
    for section, keys in _REQUIRED.items():
        if section not in cfg:
            raise ValueError(f"Config missing section: [{section}]")
        if not cfg[section]:
            raise ValueError(f"Config section [{section}] is empty.")
        for key in keys:
            if key not in cfg[section]:
                raise ValueError(f"Config missing key: [{section}].{key}")
    return cfg
