#!/usr/bin/env python3
"""Generate ``english/us_menu.asm`` -- the file-select / copy / erase /
system, relocated into the expanded ROM (bank ``$2C``).

The file-select is US code, pulled from the US disassembly (``usdasm`` bank
``$0C``); a handful of routines are pulled from the JP disassembly (``jpdasm``)
because the English build restores JP's dual-save backup the US ROM dropped.

WHY IT IS COMPACTED (not mirror-placed)
---------------------------------------
The other relocated subsystems sit at their ``+$200000`` mirror address. The
file-select cannot: two of its routines carry JP's save-backup logic and are
bigger than their US slots (``FileSelect_InitializeGFX`` 274 B vs the 85 B US
slot; ``InitializeSaveFile`` 401 B vs 176 B), so at mirror addresses they would
overrun the next routine. Instead every block is packed contiguously from
``$2C8000`` in ``BLOCK_ORDER`` -- referenced symbolically, so the exact address
does not matter, only that nothing overlaps.

CHANGES (default form; ``--baseline`` emits the pure US/JP relocation)
---------------------------------------------------------------------
* 4-character names -- the US name field is 6 wide; clamp the readers/among the
  copy loops to 4 (``SIMPLE_EDITS``), and narrow ``NamePlayerTilemap``.
* save-memory offsets -- read heart/death counts from the JP save layout.
* palette -- redirect the one ``PaletteLoadForFileSelect`` call to our overlay
  wrapper (see ``usfs_gfx.asm``); no US code needs per-frame injections.
* JP save-backup -- ``FileSelect_InitializeGFX`` / ``NameFile_EraseSave`` take
  their JP form plus small edits (``edit_initialize_gfx`` / ``edit_erase``).
* two helpers with no US top-level label are emitted verbatim (``CUSTOM``).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import TYPE_CHECKING

from snes_assembly_parser import Source, code_lines

from graft import Placement, assemble, collect_names, en_namespace

if TYPE_CHECKING:
    from snes_assembly_parser import Segment

USDASM = Path("../usdasm")
JPDASM = Path("../jpdasm")
OUT = Path("us_menu.asm")
ORG = 0x2C8000

# Blocks packed contiguously from $2C8000, in this order (US source order with
# the JP-restored save routines slotted in and tilemaps grouped at the tail).
BLOCK_ORDER = (
    "FileSelect_FairyY",
    "Module01_FileSelect",
    "FileSelect_InitializeGFX",
    "FileSelect_ReInitSaveFlagsAndGraphics",
    "ReinitializeFileSelectGraphics",
    "FileSelect_TriggerStripesAndAdvance",
    "FileSelect_Main",
    "FileSelect_SetUpNamesStripes",
    "FileSelect_HandleInput",
    "CopySaveToWRAM",
    "Module02_CopyFile",
    "CopyFile_FindFileIndices",
    "KILLFile_FindFileIndices",
    "CopyFile_ChooseSelection",
    "FileSelect_TriggerTheStripes",
    "CopyFile_ChooseTarget",
    "CopyFile_ConfirmSelection",
    "FilePicker_DeleteHeaderStripe",
    "CopyFile_FairyHeight",
    "CopyFile_CopyToMenuStripe",
    "CopyFile_TargetStripeOffsetAdjuster",
    "CopyFile_NameStripeBufferOffset",
    "CopyFile_SelectionAndBlinker",
    "CopyFile_ConfirmationStripes",
    "CopyFile_TargetFairyX",
    "CopyFile_TargetFairyY",
    "CopyFile_BufferOffset",
    "CopyFile_TargetNumerals",
    "CopyFile_TargetSelectionAndBlink",
    "CopyFile_HandleConfirmation",
    "CopyFile_CopyData",
    "KILLFile_FairyY",
    "KILL_OK_stripes",
    "KILL_OK_FileNameStripesAdjustment",
    "Module03_KILLFile",
    "KILLFile_SetUp",
    "KILLFile_HandleSelection",
    "KILLFile_HandleConfirmation",
    "KILLFile_ChooseTarget",
    "KILLFile_VerifyDeletion",
    "FileSelect_CopyNameToStripes",
    "FileSelect_DrawLink",
    "FileSelect_DrawFairy",
    "FileSelect_DrawDeaths",
    "Module04_NameFile",
    "NameFile_EraseSave",
    "NameFile_MakeScreenVisible",
    "Intro_SetStripesAndAdvance",
    "CopyFile_FairyIndent",
    "KILLFile_FairyX",
    "NameFile_CharacterLayout",
    "NameFile_CursorPositionX",
    "NameFile_CursorIndexMovementX",
    "NameFile_CursorIndexBoundaryX",
    "NameFile_CursorIndexWrapX",
    "NameFile_CursorPositionY",
    "NameFile_CursorIndexMovementY",
    "NameFile_CursorIndexBoundaryY",
    "NameFile_CursorStickY",
    "NameFile_YtoXIndexOffset",
    "NameFile_HeartXPosition",
    "NameFile_CursorMovement",
    "NameFile_DoTheNaming",
    "InitializeSaveFile",
    "NameFile_CheckForScrollInputX",
    "NameFile_CheckForScrollInputY",
    "NameFile_DrawSelectedCharacter",
    "IntroLogoTilemap",
    "FileSelectTilemap",
    "FileSelectNamesTilemap",
    "FileSelectKILLFileTilemap",
    "KILLFile_BlankNameStripes",
    "FileSelectCopyFileTilemap",
    "CopyFile_HeaderStripe",
    "CopyFile_TargetHeaderStripes",
    "NamePlayerTilemap",
    "FileSelect_UploadLinoleum",
    "FileSelect_UploadFancyBackground",
    "NameFile_FillBackground",
    "FancyBackgroundTileMap",
    "IRQActiveHandler",
)

# Blocks referenced by un-relocated code (module dispatch, save-copy, tilemap
# uploads), so they keep their bare JP name as an alias alongside the EN_ name.
HOOKS = frozenset(
    {
        "Module01_FileSelect",
        "Module02_CopyFile",
        "Module03_KILLFile",
        "Module04_NameFile",
        "CopySaveToWRAM",
        "IntroLogoTilemap",
        "FileSelectTilemap",
        "FileSelectKILLFileTilemap",
        "FileSelectCopyFileTilemap",
        "NamePlayerTilemap",
    }
)

# Routines pulled from JP (restore JP's dual-save backup the US ROM removed).
JP_BLOCKS = frozenset(
    {
        "FileSelect_InitializeGFX",
        "KILLFile_FindFileIndices",
        "NameFile_EraseSave",
        "InitializeSaveFile",
        "IntroLogoTilemap",
    }
)

# Two helpers the US source marks with scope-transparent ``#`` labels (so they
# are not top-level blocks); emitted verbatim with a real label.
CUSTOM = {
    "Intro_SetStripesAndAdvance": (
        "Intro_SetStripesAndAdvance:\nSTA.b $14\nINC.b $11\nRTS"
    ),
    "IRQActiveHandler": (
        "; [ENG-FS] V-IRQ active handler (name-entry raster split). bank_00's "
        "inline block JMLs here\n"
        "; (see base_edits.py) and we JML back to $00821B. $0128: "
        "$01=name-entry, $FF=transition.\n"
        "IRQActiveHandler:\n"
        "LDA.w TIMEUP\n"
        "LDA.w $0128\n"
        "CMP.b #$01\n"
        "BNE .default_split\n"
        "LDA.b #$74\n"
        "BRA .store_split\n"
        ".default_split\n"
        "LDA.b #$38\n"
        ".store_split\n"
        "STA.w VTIMEL\n"
        "STZ.w VTIMEH\n"
        "STZ.w HTIMEL\n"
        "STZ.w HTIMEH\n"
        "LDA.b #$A1\n"
        "STA.w NMITIMEN\n"
        "JML $00821B"
    ),
}

# Byte-neutral operand swaps: block -> [(old, new, count)].
SIMPLE_EDITS: dict[str, list[tuple[str, str, int]]] = {
    "FileSelect_HandleInput": [("LDA.l $7003E5,X", "LDA.l $7003E1,X", 1)],
    "CopyFile_SelectionAndBlinker": [("LDA.w #$0006", "LDA.w #$0004", 1)],
    "CopyFile_TargetSelectionAndBlink": [("LDA.w #$0006", "LDA.w #$0004", 1)],
    "FileSelect_CopyNameToStripes": [("LDA.w #$0006", "LDA.w #$0004", 1)],
    "FileSelect_DrawDeaths": [("LDA.l $700405,X", "LDA.l $700401,X", 1)],
    "NameFile_DoTheNaming": [
        ("LDA.b #$05", "LDA.b #$03", 1),
        ("CMP.b #$06", "CMP.b #$04", 1),
        ("CMP.w #$000A", "CMP.w #$0006", 1),
    ],
    "NamePlayerTilemap": [
        ("dw $6311, $1840", "dw $6311, $1040", 1),
        ("dw $8311, $1840", "dw $8311, $1040", 1),
        ("dw $A311, $1840", "dw $A311, $1040", 1),
        ("dw $4211, $1D00", "dw $4211, $1500", 1),
        ("dw $7011, $0580", "dw $6C11, $0580", 1),
    ],
    "ReinitializeFileSelectGraphics": [
        (
            "JSL PaletteLoadForFileSelect",
            "JSL USFS_PaletteLoadForFileSelect",
            1,
        )
    ],
}

HEADER = (
    "; english/us_menu.asm -- file-select / copy / erase / name-entry, "
    "relocated to bank $2C.\n"
    "; generated by english/generate_menu.py from ../usdasm + ../jpdasm. Do "
    "not hand-edit.\n"
    "; US code (a few routines from JP for the dual-save backup), packed "
    "contiguously from\n"
    "; $2C8000: two save routines exceed their US slots, so it cannot "
    "mirror-place."
)


def edit_initialize_gfx(block: Segment, sizes: dict[str, int]) -> None:
    """JP ``FileSelect_InitializeGFX`` -> English (name-banner + BG3 setup)."""
    # STZ.w $0AB6 -> LDA.b #$06 / STA.w $0AB6 / STA.w $0710
    block.delete("STZ.w $0AB6", "JSL PaletteLoad_UnderworldSet")
    block.insert_after(
        "STA.w $0AA9",
        code_lines(["LDA.b #$06", "STA.w $0AB6", "STA.w $0710"], sizes),
    )
    # the LDA.b #$01 before STA.w $0AB2 (not the later one) -> LDA.b #$00
    block.delete("LDA.b #$01", "STA.w $0AB2")
    block.insert_after(
        "JSL PaletteLoad_OWBG3", code_lines(["LDA.b #$00"], sizes)
    )
    # add LDA.b #$51 / STA.w $0AA2 after STA.w $0AA1
    block.insert_after(
        "STA.w $0AA1", code_lines(["LDA.b #$51", "STA.w $0AA2"], sizes)
    )


def edit_erase(block: Segment, sizes: dict[str, int]) -> None:
    """JP ``NameFile_EraseSave`` -> English (4-char blank fill + flags)."""
    # move STZ.w $0B10 from below $0B12 to right after STA.w $0128
    block.delete("STZ.w $0B10", "STZ.w $0B15")
    block.insert_after("STA.w $0128", code_lines(["STZ.w $0B10"], sizes))
    block.replace("LDA.b #$3E", "LDA.b #$83", count=1)
    block.replace("LDA.w #$019C", "LDA.w #$01F0", count=1)
    block.replace("LDA.w #$018C", "LDA.w #$00A9", count=1)


def edit_name_player_tilemap(
    block: Segment,
    sizes: dict[str, int],  # noqa: ARG001  (uniform COMPLEX_EDITS signature)
) -> None:
    """Narrow the name row of ``NamePlayerTilemap`` for the 4-char name.

    The 7-value tile row (a substring of the 8-value row above it, so not
    uniquely matchable by text) is truncated to 3 values by exact-argument
    match. The stripe header above it (edited in ``SIMPLE_EDITS``) already
    dropped the tile count to suit.
    """
    wide = ["$1587", "$1588", "$1587", "$1588", "$1587", "$1588", "$1587"]
    narrow = ["$1587", "$1588", "$1587"]
    for line in block.lines:
        if line.opcode == "dw" and line.arguments == wide:
            line.arguments = narrow
            line.arg_seps = line.arg_seps[: len(narrow) - 1]
            line.size = len(narrow) * 2
            return
    msg = "NamePlayerTilemap: wide name row not found"
    raise ValueError(msg)


COMPLEX_EDITS = {
    "FileSelect_InitializeGFX": edit_initialize_gfx,
    "NameFile_EraseSave": edit_erase,
    "NamePlayerTilemap": edit_name_player_tilemap,
}


def block_segment(
    name: str, us: Source, jp: Source, *, changes: bool
) -> Segment:
    """The one block ``name``: from CUSTOM text, or US/JP with its edits.

    A routine with an asar ``pool name`` (scoped ``.sublabel`` data) gets the
    pool emitted before the routine, matching the source layout.
    """
    if name in CUSTOM:
        return Source.from_content(CUSTOM[name].split("\n")).block(
            name, comments=False
        )
    source = jp if name in JP_BLOCKS else us
    lines = []
    if name in source.pools:
        lines += source.pool(name, comments=False).lines
    lines += source.block(name, comments=False).lines
    segment = source._segment(lines)
    if changes:
        for old, new, count in SIMPLE_EDITS.get(name, []):
            segment.replace(old, new, count)
        if name in COMPLEX_EDITS:
            COMPLEX_EDITS[name](segment, source.instruction_sizes())
    return segment


def sublabel_names(text: str, base_names: set[str]) -> set[str]:
    """Add ``Label_sublabel`` reference tokens (asar pool refs) to the set."""
    names = set(base_names)
    for base in base_names:
        names |= set(re.findall(rf"\b{re.escape(base)}_\w+", text))
    return names


def build(
    *, changes: bool, usdasm: Path = USDASM, jpdasm: Path = JPDASM
) -> str:
    us = Source.from_path(usdasm / "bank_0C.asm")
    jp = Source.from_path(jpdasm / "bank_0C.asm")

    lines = []
    for name in BLOCK_ORDER:
        if name in CUSTOM and not changes:
            continue  # the two helpers/handler are part of the graft
        lines += block_segment(name, us, jp, changes=changes).lines
    segment = us._segment(lines)

    text = segment.render(ORG)
    hooks = HOOKS if changes else frozenset()
    text = en_namespace(
        text, sublabel_names(text, collect_names(text)), hooks=hooks
    )
    return assemble(HEADER, [Placement(ORG, text, "file-select, packed.")])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--usdasm", type=Path, default=USDASM)
    parser.add_argument("--jpdasm", type=Path, default=JPDASM)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        build(
            changes=not args.baseline, usdasm=args.usdasm, jpdasm=args.jpdasm
        )
    )
    print(f"wrote {args.out} ({'baseline' if args.baseline else 'changes'})")


if __name__ == "__main__":
    main()
