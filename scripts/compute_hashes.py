#!/usr/bin/env python3
"""Computes SHA-256 hashes for all repo files and writes a markdown table to hash_report.md."""
from __future__ import annotations

import hashlib
from pathlib import Path


def main() -> None:
    root = Path(".")
    rows: list[str] = []

    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(f"| `{path.as_posix()}` | `{digest}` |")

    lines = ["| File | SHA-256 |", "|------|---------|"] + rows
    Path("hash_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Hashed {len(rows)} files.")


if __name__ == "__main__":
    main()
