#!/usr/bin/env python3
"""Append the English graft's ignore rules to a target ``.gitignore``.

The ROM-derived binaries under ``english/`` are copyrighted game data and must
not be committed (same policy as the disassembly's own ``bin/``); they are
regenerated from the user's ROMs by ``extract_english_assets.py``. Idempotent:
only rules not already present are appended.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HEADER = (
    "# --- english translation: ROM-derived assets"
    " (regenerate, don't commit) ---"
)
RULES = (
    "english/*.2bpp",
    "english/*.2bppc",
    "english/*.3bppc",
    "english/*.bin",
)


def patch(text: str) -> str:
    present = {line.strip() for line in text.splitlines()}
    missing = [rule for rule in RULES if rule not in present]
    if not missing:
        return text
    block = "\n".join([HEADER, *missing]) + "\n"
    if not text.strip():
        return block
    return text.rstrip("\n") + "\n\n" + block


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", type=Path, help=".gitignore to update in place"
    )
    args = parser.parse_args()
    original = args.path.read_text() if args.path.exists() else ""
    patched = patch(original)
    if patched == original:
        print(f"{args.path}: already ignores the English binaries (no change)")
        return 0
    args.path.write_text(patched)
    print(f"{args.path}: added English binary ignore rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
