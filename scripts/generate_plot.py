#!/usr/bin/env python3
"""Generates a bar chart of file count per extension and saves it as plot.png."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend — no display needed
import matplotlib.pyplot as plt


def main() -> None:
    root = Path(".")
    exts: Counter[str] = Counter()
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            exts[p.suffix or "(no ext)"] += 1

    labels, counts = zip(*sorted(exts.items(), key=lambda x: -x[1]))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(labels, counts, color="#0f172a")
    ax.set_title("File count by extension")
    ax.set_xlabel("Extension")
    ax.set_ylabel("Count")
    plt.tight_layout()
    plt.savefig("plot.png", dpi=120)
    print(f"Plot saved ({len(labels)} extensions, {sum(counts)} files).")


if __name__ == "__main__":
    main()
