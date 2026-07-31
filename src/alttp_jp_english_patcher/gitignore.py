#!/usr/bin/env python3
"""Append the English graft's ignore rules to a target ``.gitignore``.

The US-ROM-derived binaries under ``bin/gfx/`` (the ``us_*`` files, alongside
the disassembly's own JP-ROM-derived ones there) are copyrighted game data and
must not be committed (same policy as those); they are regenerated from the
user's ROM by ``binextract-us.py``. Battery saves (``*.srm``) are player save
state from testing the build (e.g. in an emulator), not source -- also not
committed. Idempotent: only rules not already present are appended.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BLOCKS = (
    (
        "# --- english translation: US-ROM-derived assets"
        " (regenerate, don't commit) ---",
        (
            "bin/gfx/us_*.2bpp",
            "bin/gfx/us_*.2bppc",
            "bin/gfx/us_*.3bppc",
            "bin/gfx/us_*.bin",
        ),
    ),
    (
        "# --- battery saves from testing the build (not source) ---",
        ("*.srm",),
    ),
)


def patch(text: str) -> str:
    present = {line.strip() for line in text.splitlines()}
    blocks = []
    for header, rules in _BLOCKS:
        missing = [rule for rule in rules if rule not in present]
        if missing:
            blocks.append("\n".join([header, *missing]))
    if not blocks:
        return text
    block = "\n\n".join(blocks) + "\n"
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
