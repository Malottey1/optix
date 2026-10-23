"""Repository size gate: no tracked file over 2 MB and the tracked tree under 40 MB, so originals
(design/source/, gitignored) or generated league data cannot slip in. Prints the largest file."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_FILE = 2_000_000
MAX_TOTAL = 40_000_000


def test_tracked_files_stay_small():
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    sizes = {f: (ROOT / f).stat().st_size for f in files.decode().split("\0") if f and (ROOT / f).is_file()}
    largest = max(sizes, key=sizes.get)
    print(f"largest tracked file: {largest} ({sizes[largest]} bytes); total {sum(sizes.values())} bytes")
    assert not {f: n for f, n in sizes.items() if n > MAX_FILE}
    assert sum(sizes.values()) < MAX_TOTAL
