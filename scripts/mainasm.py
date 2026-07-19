#!/usr/bin/env python3
"""Patch a pristine ``main.asm`` to include the English graft.

Inserts, right after the last bank include (``incsrc "bank_1F.asm"``):

* the ``incsrc "english/*.asm"`` lines that pull in the relocated subsystems,
* the 2 MB ROM padding + SNES header size byte the expansion needs (so the
  checksum is a plain byte-sum every emulator agrees on).

Idempotent (a second run is a no-op) and located by the bank-include line, not
a line number, so it survives upstream reformatting and fails loud if the
anchor is gone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ANCHOR = 'incsrc "bank_1F.asm"'
MARKER = 'incsrc "english/us_text.asm"'

# Order matters: us_text (engine) defines symbols the others reference.
ENGLISH_INCLUDES = (
    "us_text.asm",
    "us_menu.asm",
    "en_item_menu.asm",
    "en_credits.asm",
    "us_bank00.asm",
    "usfs_gfx.asm",
    "usgfx.asm",
)

BLOCK = (
    "",
    *(f'incsrc "english/{name}"' for name in ENGLISH_INCLUDES),
    "",
    "; [ENG-FS] Pad the ROM up to a clean 2 MB (power-of-2). The English graft"
    " expands the ROM",
    "; into banks $20-$2A, leaving it at a non-power-of-2 size (~0x150000)."
    " The SNES header",
    "; checksum for a non-power-of-2 ROM is computed by a mirror-and-sum"
    " algorithm that asar and",
    "; some emulators (e.g. snes9x) disagree on, which made snes9x report"
    ' "invalid checksum".',
    "; Padding to exactly 2 MB makes the checksum a plain byte-sum that"
    " everyone agrees on, so",
    "; --fix-checksum writes a value snes9x accepts. Banks $2B-$3F are"
    " currently unused ($00 fill);",
    "; all are valid LoROM space in a 2 MB ROM and freely usable for future"
    " English content.",
    "org $3FFFFF",
    "db $FF",
    "",
    "; Update the ROM-size byte in the SNES header to match the new 2 MB size"
    " ($0A=1 MB -> $0B=2 MB;",
    "; the field is 2^n KB). Keeps the header self-consistent with the padded"
    " file.",
    "org $00FFD7",
    "db $0B",
)


def patch(text: str) -> str:
    """Return ``main.asm`` with the English block inserted (idempotent)."""
    if MARKER in text:
        return text
    lines = text.splitlines()
    anchor = next(
        (i for i, line in enumerate(lines) if line.strip() == ANCHOR), None
    )
    if anchor is None:
        msg = f"main.asm: anchor {ANCHOR!r} not found"
        raise ValueError(msg)
    lines[anchor + 1 : anchor + 1] = list(BLOCK)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="main.asm to patch in place")
    args = parser.parse_args()
    original = args.path.read_text()
    patched = patch(original)
    if patched == original:
        print(f"{args.path}: already includes the English graft (no change)")
        return 0
    args.path.write_text(patched)
    print(f"{args.path}: inserted English includes + 2 MB padding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
