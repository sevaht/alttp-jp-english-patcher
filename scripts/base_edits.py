#!/usr/bin/env python3
"""Declarative base-disassembly edits for the English graft, applied through
the library :class:`~snes_assembly_parser.Patcher`.

The graft relocates whole subsystems into the expanded ROM (2nd MB); this
module writes the small hooks that make the unmodified JP banks reach those
relocated copies. Each bank's edits are declared here (grouped by subsystem)
and applied to a pristine ``../jpdasm`` checkout, so the base modifications are
generated -- reproducible from a clean fork -- rather than hand maintained.

Run with ``--baseline`` to leave the base untouched (the counterpart to
``generate_us_text.py --baseline``): committing the pristine base + baseline
generated files first, then the patched base + default generated files,
isolates a clean diff of exactly what the graft changes.

    ../jpdasm/bank_XX.asm  (pristine)  --[edits]-->  ./bank_XX.asm  (hooked)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from snes_assembly_parser import LandingPad, Patcher

if TYPE_CHECKING:
    from collections.abc import Callable

JPDASM = Path("../jpdasm")
OUT = Path("..")

REDIRECT_HEADER = (
    "; [ENG-REDIRECT] Landing pads: the real routines run in bank ${bank} "
    "(english/{file}).",
    "; They keep the JP entry-point names so unmodified same-bank JSR callers "
    "land here and",
    "; forward across the bank with a register-transparent JSL/RTS bridge (an "
    "argument in",
    "; A/X/Y passes straight through); the JP originals are preserved "
    "above as UNREACHABLE_*.",
)


def redirect(bank: str, file: str) -> tuple[str, ...]:
    return tuple(line.format(bank=bank, file=file) for line in REDIRECT_HEADER)


def en_pad(name: str, comment: tuple[str, ...] = ()) -> LandingPad:
    """A landing pad forwarding the freed JP ``name`` to its ``EN_`` copy."""
    return LandingPad(name, f"EN_{name}", comment)


# ---- TEXT subsystem: engine relocated to bank $2E (generate_us_text.py) ----
def edit_bank_0e(patcher: Patcher) -> None:
    # Credits routines relocated to en_credits.asm; free the names, then fill
    # the free-ROM hole with forwarding pads.
    patcher.free("Credits_AddNextAttribution")
    patcher.free("Credits_AddEndingSequenceText")
    patcher.landing_pads(
        "NULL_0EEDFB",
        [
            en_pad("Credits_AddNextAttribution"),
            en_pad("Credits_AddEndingSequenceText"),
        ],
        header=redirect("2E", "en_credits.asm"),
    )
    # Text-engine hooks: the bare names are claimed by us_text.asm at the +$20
    # mirror; free the JP originals so JP callers resolve to our copy.
    for name in (
        "RenderText",
        "Module0E_02_RenderText",
        "DecompressFontGFX",
        "BuildSomeTextMasks",
    ):
        patcher.free(name)


def edit_bank_1c(patcher: Patcher) -> None:
    # JP keeps CreateMessagePointers here (US had it in bank_0E); free it.
    patcher.free("CreateMessagePointers")


# ---- FONT + FILE-SELECT: bank_00 hooks, file-select relocated to bank $2C ---
def edit_bank_00(patcher: Patcher) -> None:
    # V-IRQ active block: one JML redirects it to the relocated handler
    # (english/us_menu.asm), which picks the name-entry raster-split scanline
    # and JMLs back to $00821B. The JML overwrites only the first instruction
    # (LDA.w TIMEUP) and the opcode of the next (LDA.b #$38, whose $38 operand
    # is orphaned at $008209); the rest of the block stays as the original,
    # now-dead JP instructions.
    patcher.relocate_block(
        0x008205,
        "EN_IRQActiveHandler",
        resume=0x00820A,
        orphan=(0x38,),
        comment=(
            "; [ENG-FS] V-IRQ active block -> relocated handler in bank $2C "
            "(us_menu.asm).",
        ),
    )
    # File-select play area: US BG3 blank tile $00A9 (JP $0188 was a hex
    # glyph that rendered the US-style play area brown instead of black).
    patcher.set_operand(
        0x008335,
        "LDA.w #$00A9",
        comment="[ENG-FS] US BG3 blank tile (was $0188 hex-pattern glyph)",
    )
    # Text box tile count: the US text engine draws a 126-tile box (JP 120);
    # fixes a stale bottom-right tile.
    patcher.set_operand(
        0x008D02,
        "LDX.w #$07E0",
        comment="[ENG-TEXT] US 126-tile text box (was $0780 / 120)",
    )
    # Font upload: point the VRAM $E000 upload at our TheFont (JP uploaded a
    # $7E2000 VWF buffer that the US path does not build).
    patcher.set_operand(0x00E557, "LDA.b #TheFont>>16")
    patcher.set_operand(0x00E563, "LDA.w #TheFont")
    patcher.set_operand(0x00E568, "LDX.w #(TheFont_end-TheFont)/2-1")
    # TransferFontToVRAM is relocated to bank $20 (us_bank00.asm); free it.
    patcher.free("TransferFontToVRAM")


def edit_bank_0c(patcher: Patcher) -> None:
    # File-select modules relocated/compacted to bank $2C (us_menu.asm). Re-pin
    # the FairyY data left behind, free the module names, and repoint the one
    # in-bank reference at the preserved JP copy.
    patcher.insert_before("FileSelect_FairyY", ["org $0CCC67"])
    for name in (
        "Module01_FileSelect",
        "CopySaveToWRAM",
        "Module02_CopyFile",
        "Module03_KILLFile",
        "Module04_NameFile",
        "IntroLogoTilemap",
        "FileSelectTilemap",
        "FileSelectKILLFileTilemap",
        "FileSelectCopyFileTilemap",
        "NamePlayerTilemap",
    ):
        patcher.free(name)
    patcher.rewrite_reference(
        0x0CCE8B, "CopySaveToWRAM", "UNREACHABLE_CopySaveToWRAM"
    )


# ---- ITEM MENU: relocated to bank $2D (en_item_menu.asm) --------------------
def edit_bank_0d(patcher: Patcher) -> None:
    for name in (
        "UpdateBottleMenu",
        "DrawAbilityText",
        "SetLiftText",
        "DrawEquippedYItem",
    ):
        patcher.free(name)
    patcher.landing_pads(
        "NULL_0DAFDD",
        [
            en_pad("UpdateBottleMenu"),
            en_pad("DrawAbilityText"),
            en_pad("SetLiftText"),
            en_pad("DrawEquippedYItem"),
        ],
        header=redirect("2D", "en_item_menu.asm"),
    )


# ---- GRAPHICS: JP menu sheets repointed at US art (usgfx.asm) ---------------
def edit_bank_13(patcher: Patcher) -> None:
    patcher.free(
        "GFX_39",
        comment=(
            "; [ENG-GFX] JP menu-bg sheet $39 repointed at the US linoleum "
            "(GFX_39, usgfx.asm);",
            "; this JP data is no longer referenced.",
        ),
    )


def edit_bank_18(patcher: Patcher) -> None:
    patcher.free(
        "GFX_DC",
        comment=(
            "; [ENG-GFX] JP menu-font sheet $69 repointed at the US font "
            "(GFX_DC, usgfx.asm).",
        ),
    )
    patcher.free(
        "GFX_DD",
        comment=(
            "; [ENG-GFX] JP $6A repointed at the US font (GFX_DD, usgfx.asm); "
            "data stays live via GFX_71.",
        ),
    )


BANK_EDITS: dict[str, Callable[[Patcher], None]] = {
    "bank_00": edit_bank_00,
    "bank_0C": edit_bank_0c,
    "bank_0D": edit_bank_0d,
    "bank_0E": edit_bank_0e,
    "bank_13": edit_bank_13,
    "bank_18": edit_bank_18,
    "bank_1C": edit_bank_1c,
}


def apply_all(src: Path, dst: Path) -> list[str]:
    """Patch each declared bank from ``src`` into ``dst``; return names."""
    for bank, edit in BANK_EDITS.items():
        patcher = Patcher.from_path(src / f"{bank}.asm")
        edit(patcher)
        patcher.save(dst / f"{bank}.asm")
    return list(BANK_EDITS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="leave the base disassembly pristine (apply no hooks)",
    )
    parser.add_argument(
        "--src", type=Path, default=JPDASM, help="pristine base"
    )
    parser.add_argument("--dst", type=Path, default=OUT, help="output base")
    args = parser.parse_args()
    if args.baseline:
        print("baseline: base disassembly left pristine")
        return
    banks = apply_all(args.src, args.dst)
    print(f"patched {len(banks)} banks: {', '.join(banks)}")


if __name__ == "__main__":
    main()
