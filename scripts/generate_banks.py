#!/usr/bin/env python3
"""Generate the English graft as ``bank_XX.asm`` files -- one per expanded-ROM
bank, following the disassembly's one-file-per-bank convention.

Every subsystem generator returns a :class:`~graft.Relocation` that knows where
each of its pieces lands (its ``org``). This orchestrator collects those pieces
from all of them and lets :func:`~graft.write_banks` group them by ROM bank, so
the graft slots in beside the base ``bank_00.asm`` .. ``bank_1F.asm`` as
``bank_20.asm`` .. ``bank_2E.asm`` -- no subsystem still owns a file, the bank
does.

The generated banks are:

* ``bank_20`` -- our VWF font + the relocated ``TransferFontToVRAM``
* ``bank_22`` / ``bank_23`` -- the message data (main table + overflow)
* ``bank_26`` -- the US menu/HUD + file-select graphics sheets
* ``bank_27`` -- the file-select US palette overlay + data
* ``bank_2C`` -- the file-select / copy / erase / name-entry
* ``bank_2D`` -- the item menu
* ``bank_2E`` -- the text engine (+ override stubs) and the credits
"""

from __future__ import annotations

import argparse
from pathlib import Path

import generate_bank00
import generate_credits
import generate_fs_palette
import generate_gfx
import generate_item_menu
import generate_menu
import generate_us_text
from graft import Placement, write_banks

USDASM = Path("../usdasm")
JPDASM = Path("../jpdasm")
OUT = Path()


def build(
    *, changes: bool, usdasm: Path = USDASM, jpdasm: Path = JPDASM
) -> list[Placement]:
    """Every subsystem's placed, ``EN_``-namespaced pieces, in one list."""
    relocations = [
        generate_us_text.build(changes=changes, usdasm=usdasm),
        generate_bank00.build(changes=changes, jpdasm=jpdasm),
        generate_credits.build(changes=changes, jpdasm=jpdasm, usdasm=usdasm),
        generate_item_menu.build(
            changes=changes, jpdasm=jpdasm, usdasm=usdasm
        ),
        generate_menu.build(changes=changes, usdasm=usdasm, jpdasm=jpdasm),
        generate_gfx.build(changes=changes),
        generate_fs_palette.build(changes=changes),
    ]
    return [
        placement
        for relocation in relocations
        for placement in relocation.placements()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="emit the change-free baseline (no graft edits or hook aliases)",
    )
    parser.add_argument("--usdasm", type=Path, default=USDASM)
    parser.add_argument("--jpdasm", type=Path, default=JPDASM)
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT,
        help="directory to write the bank_XX.asm files into",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    placements = build(
        changes=not args.baseline, usdasm=args.usdasm, jpdasm=args.jpdasm
    )
    written = write_banks(placements, args.out)
    mode = "baseline" if args.baseline else "with changes"
    print(f"wrote {len(written)} banks ({mode}): {', '.join(written)}")


if __name__ == "__main__":
    main()
