#!/usr/bin/env python3
"""Generate the English graft as ``bank_XX.asm`` files -- one per expanded-ROM
bank, following the disassembly's one-file-per-bank convention.

Each function below builds one relocated subsystem as a
:class:`graft.Relocation`
(its placed, ``EN_``-namespaced pieces, each knowing the ``org`` it lands at);
:func:`placements` collects them all and :func:`graft.write_banks` groups
them by
ROM bank into ``bank_20`` .. ``bank_2E``, beside the base ``bank_00`` ..
``bank_1F``. The code is pulled *by name* from the US/JP disassembly
(``../usdasm``, ``../jpdasm``); the binary assets (font, graphics, palette) are
US-ROM byte slices ``incbin``\\ 'd from ``english/`` (via
``extract_english_assets.py``). Each subsystem is self-contained -- its
constants, helpers, and edits live in its own function -- so there is nothing
file-wide to trace through.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from snes_assembly_parser import (
    Assembly,
    Block,
    Line,
    Pool,
    data,
    datas,
    instructions,
    note,
    notes,
)

from graft import Placement, Relocation, mirror, substitute, write_banks

USDASM = Path("../usdasm")
JPDASM = Path("../jpdasm")


def text(usdasm: Path, *, changes: bool) -> Relocation:
    """The US text subsystem: the VWF font (bank ``$20``), the message engine
    (mirror-placed to ``$2E``), and the message data (``$22``/``$23``).

    The engine is pulled whole from ``ENGINE_ROOTS`` by reference; the two
    endpoints plus ``TextCommandLengths`` (reached only by an out-of-bounds
    index) close over the entire live subsystem. Dead blocks drop out, their
    space held with an ``org`` so survivors keep their +$200000 mirror address.
    """
    engine_roots = (
        "RenderText",
        "CreateMessagePointers",
        "TextCommandLengths",
    )
    engine_hooks = frozenset(
        {"RenderText", "Module0E_02_RenderText", "CreateMessagePointers"}
    )
    shared = frozenset({"TheFont", "TheFont_end"})  # left un-namespaced
    gap_notes = {
        "UNREACHABLE_0ED3CF": (
            "CreateMessagePointers over-reads "
            "RenderText_MoreInitialSettings,Y up to index $7F (past its "
            "20-byte end) across this pad into TextCommandLengths just "
            "below, so this offset is load-bearing."
        )
    }
    decompress_hook = 0x0EF572  # JP DecompressFontGFX
    masks_hook = 0x0EFCB2  # JP BuildSomeTextMasks

    def edit_engine(engine: Assembly) -> None:
        # (1) [NAME] field: JP names are 4 chars, the stock US handler 6 wide.
        # Read/filter only 4, copy the 4 real slots (below), then drop the 2
        # unused field slots (DEX DEX) and trim. The two slot-5/6 copy writes
        # become DEX DEX + NOP ($EA) fill of the SAME 12 bytes, so the routine
        # stays byte-identical to stock US -- nothing downstream shifts.
        engine.replace("CPY.w #$0006", "CPY.w #$0004", count=2)
        engine.replace("LDY.w #$0005", "LDY.w #$0003", count=1)
        engine.delete("LDA.b $0C", ";---")  # cut slot-5/6 writes (12 bytes)
        engine.insert_after(
            "STA.l $7F11FD,X",
            notes(
                [
                    "",
                    "; [ENG-FS] The 4 real name slots are copied above; drop"
                    " the",
                    "; 2 unused slots of the 6-wide US [NAME] field (DEX DEX)"
                    " so",
                    "; the trim rewinds to the real width. The db is NOP "
                    "($EA)",
                    "; fill, keeping this routine the same length as stock US,"
                    " in",
                    "; place of the two cut copy writes, so nothing "
                    "downstream",
                    "; shifts.",
                ]
            )
            + instructions(["DEX", "DEX"])
            + [data("db $EA, $EA, $EA, $EA, $EA, $EA, $EA, $EA, $EA, $EA")],
        )
        engine.annotate(
            "ADC.w #$0006",
            "[ENG-FS] advance by the US 6-wide field; DEX DEX below "
            "trims to 4",
        )
        engine.annotate(
            "LDY.w #$0003",
            "[ENG-FS] trim trailing spaces across the 4-char [NAME] field",
        )
        # (2) repoint RenderText_Choose2HighOr3's cursor prompts to the
        # re-appended copies
        engine.replace(
            "dw $000B",
            "dw $018B    ; [ENG-TEXT] was $000B -> Message_Choose2High_opt1",
            count=1,
        )
        engine.replace(
            "dw $000C",
            "dw $018C    ; [ENG-TEXT] was $000C -> Message_Choose2High_opt2",
            count=1,
        )

    def cursor_messages() -> list[Line]:
        # The two Choose2High cursor prompts, re-appended past JP's ID range,
        # terminated by $FF (the marker CreateMessagePointers scans for).
        rule = ";" + "=" * 99
        return [
            *notes(
                [
                    rule,
                    "; [ENG-TEXT] Restored Choose2High cursor-prompt messages"
                    " (US",
                    "; Message_000B/000C). The ID realignment drops US-only",
                    "; 000B/000C so message IDs match JP, but the US engine's",
                    "; RenderText_Choose2HighOr3 references them by ID for "
                    "the",
                    "; selection cursor. Re-appended at the next free IDs",
                    "; (395=$18B, 396=$18C, past JP's 0-394). Without this, a",
                    "; 2-option 'high' prompt (e.g. the Great Fairy upgrade)",
                    "; loaded whatever now sits at ID $000B as glitch text.",
                    "; ID $018B (395) -- cursor '>' on line 2",
                    "Message_Choose2High_opt1:",
                ]
            ),
            *datas(
                [
                    "db $7A, $00 ; set draw speed",
                    "db $76 ; line 3",
                    "db $88 ; [    ]",
                    "db $75 ; line 2",
                    "db $8A, $44 ; [  ]>",
                    "db $6F ; choose 2 high",
                    "db $7F ; end of message",
                ]
            ),
            *notes(
                [
                    "",
                    "Message_Choose2High_opt2:            ; ID $018C (396) -- "
                    "cursor '>' on line 3",
                ]
            ),
            *datas(
                [
                    "db $7A, $00 ; set draw speed",
                    "db $75 ; line 2",
                    "db $88 ; [    ]",
                    "db $76 ; line 3",
                    "db $8A, $44 ; [  ]>",
                    "db $6F ; choose 2 high",
                    "db $7F ; end of message",
                ]
            ),
            *notes([""]),
            *datas(
                [
                    "db $FF ; end of message table "
                    "(CreateMessagePointers terminator)"
                ]
            ),
        ]

    bank_0e = Assembly.from_path(usdasm / "bank_0E.asm")
    text_asm = Assembly.from_path(usdasm / "text.asm")

    engine = bank_0e.extract(
        engine_roots,
        recursive=True,
        external=shared,
        comments=True,
        gap_notes=gap_notes,
    )
    if changes:
        edit_engine(engine)
    start = engine.start_address
    if start is None:
        msg = "engine has no address anchor"
        raise ValueError(msg)
    engine_org = mirror(start)  # $0EC440 -> $2EC440

    main = text_asm.blocks_until("Message_Data")
    overflow = text_asm.blocks_until("Message_DataExtra")
    if changes:
        main.delete_block("Message_000B")  # drop US-only cursor messages,
        main.delete_block("Message_000C")  # so game-code message IDs match JP
        overflow.append(cursor_messages())  # re-appended past JP's ID range

    # The engine re-caption is a multi-line comment swap, done on the engine's
    # rendered text (placed as a str). One global EN_ namespace keeps
    # cross-block
    # refs (engine <-> data) in step; the bare hook aliases and override stubs
    # are graft-only, so a baseline build emits neither.
    engine_text = engine.render(engine_org)
    if changes:
        engine_text = substitute(
            engine_text,
            "; I hate this thing...",
            "\n".join(  # noqa: FLY002
                [
                    "; [ENG-NAME] Names are entered on the US file-select"
                    " screen, so they",
                    "; store native US character codes. This is the stock US",
                    "; RenderText_FilterName (maps name-entry codes to VWF"
                    " glyph codes,",
                    "; I/i and '!' special cases + the lowercase-encode"
                    " branch).",
                ]
            ),
        )

    overflow_note = "MESSAGE overflow (US bank_0E)"
    overflow_note += " + re-appended cursor prompts." if changes else "."

    relocation = Relocation(
        hooks=engine_hooks if changes else frozenset(), shared=shared
    )
    # Our VWF text font (font.2bpp); a raw blob (TheFont/TheFont_end stay bare,
    # shared), read by the engine and the bank_00 upload.
    relocation.place(
        'TheFont:\n    incbin "english/font.2bpp"\nTheFont_end:',
        0x208000,
        "Our VWF text font (font.2bpp); read by the bank_00 upload.",
        namespace=False,
    )
    relocation.place(
        engine_text,
        engine_org,
        "Text ENGINE, mirror-placed from US bank_0E $0EC440.",
    )
    if changes:
        # Override stubs, hand-written in final form (own bare hook alias +
        # EN_ name), so emitted verbatim.
        relocation.place(
            "; [ENG-FSFONT] JP's DecompressFontGFX VWF-rendered the JP font"
            " into $7E2000; the US ROM has no\n"
            "; such routine -- its text font is the plain 2bpp TheFont,"
            " uploaded to VRAM $E000 by\n"
            "; TransferFontToVRAM. So this override is just a tail-call.\n"
            "DecompressFontGFX:\n"
            "EN_DecompressFontGFX:\n"
            f"#_{mirror(decompress_hook):06X}: JML EN_TransferFontToVRAM"
            "       ; upload TheFont, then RTL",
            mirror(decompress_hook),
            "Hook: DecompressFontGFX (mirror of JP $0EF572).",
            namespace=False,
        )
        relocation.place(
            "; [ENG-TEXT] BuildSomeTextMasks is a no-op here (masks come from"
            " the PerformVWFing tables);\n"
            "; keep the hook so its JP callers land somewhere valid.\n"
            "BuildSomeTextMasks:\n"
            "EN_BuildSomeTextMasks:\n"
            f"#_{mirror(masks_hook):06X}: RTL",
            mirror(masks_hook),
            "Hook: BuildSomeTextMasks (mirror of JP $0EFCB2).",
            namespace=False,
        )
    relocation.place(
        main, 0x228000, "MESSAGE data (US text.asm bank $1C); free bank."
    )
    relocation.place(overflow, 0x238000, overflow_note)
    return relocation


def font_upload(jpdasm: Path, *, changes: bool) -> Relocation:
    """Bank ``$20``: JP ``TransferFontToVRAM``, mirror-placed and repointed to
    upload our plain-2bpp ``TheFont`` to VRAM $E000 (was a $7E2000 VWF buffer).
    """
    root = "TransferFontToVRAM"
    shared = frozenset({"TheFont", "TheFont_end"})
    routine = Assembly.from_path(jpdasm / "bank_00.asm").extract(
        [root], recursive=True, external=shared
    )
    start = routine.start_address
    if start is None:
        msg = f"{root} has no address anchor"
        raise ValueError(msg)
    if changes:
        # The three font-source operands, same byte width so length is
        # unchanged.
        routine.replace("LDA.b #$7E", "LDA.b #TheFont>>16", count=1)
        routine.replace("LDA.w #$7E2000", "LDA.w #TheFont", count=1)
        routine.replace(
            "LDX.w #$0FFF", "LDX.w #(TheFont_end-TheFont)/2-1", count=1
        )
        routine.lines.insert(
            0,
            note(
                "; [ENG-GFX] Uploads TheFont (font.2bpp) to VRAM $E000 -- the"
                " US form (JP uploaded a $7E2000 VWF buffer)."
            ),
        )
    relocation = Relocation(
        hooks=frozenset({root}) if changes else frozenset(), shared=shared
    )
    relocation.place(
        routine,
        mirror(start),
        "bank-$00 TransferFontToVRAM (mirror of JP $00E596).",
    )
    return relocation


def credits_bank(jpdasm: Path, usdasm: Path, *, changes: bool) -> Relocation:
    """Bank ``$2E``: the JP credits reader + tables, mirror-placed, with the
    glyph map swapped to the US table so credits render in the US Latin font.

    Placed in three contiguous groups (JP interleaves them with credits code we
    do not relocate). The readers return long -- they are reached across banks
    via bank_0E landing pads -- and keep only their EN_ names (the bare aliases
    live under the pads in bank_0E), so no hooks/shared here.
    """
    # (blocks/pools of a group, then the leading names whose dw glyph-tile
    # values come from the US font layout -- same length, so byte-neutral).
    groups: tuple[tuple[tuple[Block | Pool, ...], tuple[str, ...]], ...] = (
        (
            (
                Block("Credits_CharacterToTile"),
                Block("CreditsBlankFillTile"),
                Pool("CreditsTextLine"),
            ),
            ("Credits_CharacterToTile", "CreditsBlankFillTile"),
        ),
        (
            (
                Pool("Credits_AddNextAttribution"),
                Block("Credits_AddNextAttribution"),
            ),
            ("Credits_AddNextAttribution",),
        ),
        (
            (
                Pool("Credits_AddEndingSequenceText"),
                Block("Credits_AddEndingSequenceText"),
            ),
            (),  # ending-sequence tilemap keeps JP palette attributes
        ),
    )
    readers = ("Credits_AddNextAttribution", "Credits_AddEndingSequenceText")

    def us_glyph_values(
        us_bank: Assembly, names: tuple[str, ...]
    ) -> list[list[str]]:
        # The dw operand lists of the named US blocks/pools, in order (pool
        # data before block, matching Assembly.concat).
        values: list[list[str]] = []
        for name in names:
            segments = []
            if name in us_bank.pools:
                segments.append(us_bank.pool(name, comments=False))
            if name in us_bank.labels:
                segments.append(us_bank.function(name, comments=False))
            for segment in segments:
                values += [
                    line.arguments
                    for line in segment.lines
                    if line.opcode == "dw"
                ]
        return values

    def splice_us_glyphs(group: Assembly, values: list[list[str]]) -> None:
        # Overwrite the group's leading dw values with the US glyph tiles (same
        # length in JP and US, so byte-neutral); JP text data below is kept.
        index = 0
        for line in group.lines:
            if line.opcode == "dw" and index < len(values):
                line.arguments = values[index]
                index += 1
        if index != len(values):
            msg = f"glyph splice: wrote {index} of {len(values)} entries"
            raise ValueError(msg)

    def return_long(group: Assembly) -> None:
        # The group's final RTS -> RTL (same size).
        for line in reversed(group.lines):
            if line.opcode == "RTS":
                line.opcode = "RTL"
                return
            if line.opcode is not None:
                break
        msg = "return_long: group does not end in RTS"
        raise ValueError(msg)

    jp_bank = Assembly.from_path(jpdasm / "bank_0E.asm")
    us_bank = Assembly.from_path(usdasm / "bank_0E.asm")
    relocation = Relocation()
    for blocks, glyph_blocks in groups:
        group = jp_bank.concat(list(blocks))
        start = group.start_address
        if start is None:
            msg = f"group {blocks[0].name} has no address anchor"
            raise ValueError(msg)
        if changes:
            splice_us_glyphs(group, us_glyph_values(us_bank, glyph_blocks))
            if any(block.name in readers for block in blocks):
                return_long(group)
        relocation.place(
            group,
            mirror(start),
            f"credits group at mirror of JP ${start:06X}.",
        )
    return relocation


def item_menu(usdasm: Path, jpdasm: Path, *, changes: bool) -> Relocation:
    """Bank ``$2D``: the US item menu, mirror-placed. Four entry routines get a
    DBR-setting trampoline (their bodies become ``<name>_body`` and return
    long);
    the name-text tables get the US content, with the 2-row US ``Mirror`` table
    duplicated to JP's 4-row slot (cascading the rest forward $20 bytes).
    """
    entries = (
        "UpdateBottleMenu",
        "DrawAbilityText",
        "SetLiftText",
        "DrawEquippedYItem",
    )
    # (US block, EN name, return-long). Entry routines -> <name>_body.
    bodies = (
        ("BottleMenuCursorPosition", "BottleMenuCursorPosition", False),
        ("UpdateBottleMenu", "UpdateBottleMenu_body", True),
        ("DrawMenuIcon", "DrawMenuIcon", False),
        ("DrawAbilityText", "DrawAbilityText_body", True),
        ("SetLiftText", "SetLiftText_body", True),
        ("DrawEquippedYItem", "DrawEquippedYItem_body", True),
    )
    # One contiguous US region so the Mirror expansion cascades the rest
    # exactly.
    name_text = (
        "ItemMenuNameText_YItems",
        "ItemMenuNameText_Bottles",
        "ItemMenuNameText_Powder",
        "ItemMenuNameText_Flute",
        "ItemMenuNameText_Mirror",
        "ItemMenuNameText_Bow",
        "ItemIcons",
        "AbilityText",
    )

    def trampolines() -> Assembly:
        # Four DBR-setting redirect stubs; bare names (namespaced to EN_
        # uniformly), anchors stamped when placed.
        lines: list[Line] = []
        for name in entries:
            lines.append(note(f"{name}:"))
            lines += instructions(["PHB", "PHK", "PLB", f"JMP.w {name}_body"])
        return Assembly(lines)

    def return_long(segment: Assembly) -> None:
        # Final RTS -> PLB + RTL (restore the caller's DBR before returning).
        for index in range(len(segment.lines) - 1, -1, -1):
            line = segment.lines[index]
            if line.opcode == "RTS":
                line.opcode, line.arguments = "PLB", []
                rtl = Line.from_line(f"#_{line.address:06X}: RTL")
                rtl.size = 1
                segment.lines.insert(index + 1, rtl)
                return
            if line.opcode is not None:
                break
        msg = "return_long: body does not end in RTS"
        raise ValueError(msg)

    def duplicate_mirror(region: Assembly) -> None:
        # US ItemMenuNameText_Mirror is 2 dw rows; the JP slot wants 4, so copy
        # the 2 rows once more (byte-for-byte, cascading the rest $20 forward).
        start = next(
            index
            for index, line in enumerate(region.lines)
            if line.label and line.label.endswith("ItemMenuNameText_Mirror")
        )
        end = next(
            index
            for index in range(start + 1, len(region.lines))
            if region.lines[index].is_top_level_label
        )
        rows = [
            line for line in region.lines[start:end] if line.opcode == "dw"
        ]
        if len(rows) != 2:  # noqa: PLR2004
            msg = f"Mirror: expected 2 US rows, found {len(rows)}"
            raise ValueError(msg)
        copies = [Line.from_line(str(row)) for row in rows]
        for copy, row in zip(copies, rows, strict=True):
            copy.size = row.size
        region.lines[end:end] = copies

    def patch_ability_text(region: Assembly, jp_bank: Assembly) -> None:
        # Rows 10-11 of AbilityText keep the JP tile values (not US).
        jp_rows = [
            line.arguments
            for line in jp_bank.function("AbilityText", comments=False).lines
            if line.opcode == "dw"
        ]
        row = 0
        inside = False
        for line in region.lines:
            if line.label and line.label.endswith("AbilityText"):
                inside = True
                continue
            if inside and line.is_top_level_label:
                break
            if inside and line.opcode == "dw":
                if row in (10, 11):
                    line.arguments = jp_rows[row]
                row += 1

    us_bank = Assembly.from_path(usdasm / "bank_0D.asm")
    jp_bank = Assembly.from_path(jpdasm / "bank_0D.asm")
    relocation = Relocation()

    def place(body: Assembly, org: int) -> None:
        relocation.place(body, org, f"item-menu @ ${org:06X}.")

    if changes:
        place(trampolines(), 0x2DE100)
    for us_name, en_name, long_return in bodies:
        body = us_bank.function(us_name, comments=False)
        start = body.start_address
        if start is None:
            msg = f"{us_name} has no address anchor"
            raise ValueError(msg)
        if changes and long_return:
            return_long(body)
        if en_name != us_name:
            body.lines[0].label = en_name  # rename the routine label
        place(body, mirror(start))

    region = us_bank.concat([*name_text])
    region_start = region.start_address
    if region_start is None:
        msg = "name-text region has no address anchor"
        raise ValueError(msg)
    if changes:
        duplicate_mirror(region)
        patch_ability_text(region, jp_bank)
    place(region, mirror(region_start))

    cursor = us_bank.function("MenuCursorPositions", comments=False)
    cursor_start = cursor.start_address
    if cursor_start is None:
        msg = "MenuCursorPositions has no address anchor"
        raise ValueError(msg)
    shift = 0x20 if changes else 0  # Mirror grew by $20 (2 rows)
    place(cursor, mirror(cursor_start) + shift)
    return relocation


def file_select(usdasm: Path, jpdasm: Path, *, changes: bool) -> Relocation:
    """Bank ``$2C``: the US file-select / copy / erase / name-entry, packed
    contiguously from ``$2C8000`` (two JP-restored save routines are too big
    for
    their US slots to mirror-place). Pulled whole by recursion from the entry
    points; a few come from JP for the dual-save backup the US dropped.
    """
    # The entry points -- every symbol un-relocated code reaches this subsystem
    # by. They are both the recursion ROOTS (closure pulls the transitive
    # helpers/data) and the HOOKS kept bare so unmodified callers resolve.
    hooks = frozenset(
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
    # Pulled from JP (restore the dual-save backup the US ROM removed).
    jp_blocks = frozenset(
        {
            "FileSelect_InitializeGFX",
            "KILLFile_FindFileIndices",
            "NameFile_EraseSave",
            "InitializeSaveFile",
            "IntroLogoTilemap",
        }
    )
    # Two helpers the US source marks with scope-transparent # labels (not
    # top-level blocks); emitted verbatim with a real label.
    custom = {
        "Intro_SetStripesAndAdvance": (
            "Intro_SetStripesAndAdvance:\nSTA.b $14\nINC.b $11\nRTS"
        ),
        "IRQActiveHandler": (
            "; [ENG-FS] V-IRQ active handler (name-entry raster split)."
            " bank_00's inline block JMLs here\n"
            "; (see base_edits.py) and we JML back to $00821B. $0128:"
            " $01=name-entry, $FF=transition.\n"
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
    simple_edits: dict[str, list[tuple[str, str, int]]] = {
        "FileSelect_HandleInput": [("LDA.l $7003E5,X", "LDA.l $7003E1,X", 1)],
        "CopyFile_SelectionAndBlinker": [("LDA.w #$0006", "LDA.w #$0004", 1)],
        "CopyFile_TargetSelectionAndBlink": [
            ("LDA.w #$0006", "LDA.w #$0004", 1)
        ],
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

    def edit_initialize_gfx(block: Assembly) -> None:
        # JP FileSelect_InitializeGFX -> English (name-banner + BG3 setup).
        block.delete("STZ.w $0AB6", "JSL PaletteLoad_UnderworldSet")
        block.insert_after(
            "STA.w $0AA9",
            instructions(["LDA.b #$06", "STA.w $0AB6", "STA.w $0710"]),
        )
        block.delete("LDA.b #$01", "STA.w $0AB2")
        block.insert_after(
            "JSL PaletteLoad_OWBG3", instructions(["LDA.b #$00"])
        )
        block.insert_after(
            "STA.w $0AA1", instructions(["LDA.b #$51", "STA.w $0AA2"])
        )

    def edit_erase(block: Assembly) -> None:
        # JP NameFile_EraseSave -> English (4-char blank fill + flags).
        block.delete("STZ.w $0B10", "STZ.w $0B15")
        block.insert_after("STA.w $0128", instructions(["STZ.w $0B10"]))
        block.replace("LDA.b #$3E", "LDA.b #$83", count=1)
        block.replace("LDA.w #$019C", "LDA.w #$01F0", count=1)
        block.replace("LDA.w #$018C", "LDA.w #$00A9", count=1)

    def edit_name_player_tilemap(block: Assembly) -> None:
        # Narrow NamePlayerTilemap's 7-value name row to 3 (the 4-char name);
        # matched by exact argument (it is a substring of the row above it).
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

    complex_edits = {
        "FileSelect_InitializeGFX": edit_initialize_gfx,
        "NameFile_EraseSave": edit_erase,
        "NamePlayerTilemap": edit_name_player_tilemap,
    }

    def block_segment(name: str) -> Assembly:
        # One block: CUSTOM text, or US/JP with edits (pool before routine).
        if name in custom:
            return Assembly.from_content(custom[name].split("\n")).function(
                name, comments=False
            )
        source = jp_bank if name in jp_blocks else us_bank
        lines = []
        if name in source.pools:
            lines += source.pool(name, comments=False).lines
        lines += source.function(name, comments=False).lines
        segment = Assembly(lines)
        if changes:
            for old, new, count in simple_edits.get(name, []):
                segment.replace(old, new, count)
            if name in complex_edits:
                complex_edits[name](segment)
        return segment

    us_bank = Assembly.from_path(usdasm / "bank_0C.asm")
    jp_bank = Assembly.from_path(jpdasm / "bank_0C.asm")

    # Emitted in US source order: absolute addresses do not matter (symbolic
    # references), and source order keeps the few fall-through routines next to
    # their successor. The label-less helpers have no symbol to recurse to.
    reachable = us_bank.closure(sorted(hooks), recursive=True)
    block_order = list(
        dict.fromkeys(
            entry.name for entry in reachable if isinstance(entry, Block)
        )
    )
    if changes:
        block_order += list(custom)

    lines = []
    for name in block_order:
        lines += block_segment(name).lines
    relocation = Relocation(hooks=hooks if changes else frozenset())
    relocation.place(Assembly(lines), 0x2C8000, "file-select, packed.")
    return relocation


def graphics(*, changes: bool) -> Relocation:
    """Bank ``$26``: the US menu/HUD + file-select graphics sheets (the
    kana/Latin font sheets ``GFX_DC``/``GFX_DD`` and the file-select "linoleum"
    JP-vs-US kana/Latin font sheets ``GFX_DC``/``GFX_DD`` and the file-select
    "linoleum" background ``GFX_39``). Binary US-ROM slices, ``incbin``\\ 'd;
    each claims its freed JP name so the game's tables reach the US art.
    """
    # (JP sheet name, its US-ROM slice, extracted into english/). Packed from
    # $268000; referenced by symbol, so the exact address is asar's job.
    sheets = (
        ("GFX_DC", "gfx_dc.2bppc"),  # US menu / file-select font sheet ($69)
        ("GFX_DD", "gfx_dd.2bppc"),  # US menu / file-select font sheet ($6A)
        ("GFX_39", "gfx_39.3bppc"),  # US file-select "linoleum" bg ($39)
    )
    body = "\n\n".join(
        f'{name}:\n    incbin "english/{asset}"' for name, asset in sheets
    )
    relocation = Relocation(
        hooks=frozenset(name for name, _ in sheets) if changes else frozenset()
    )
    relocation.place(
        body, 0x268000, "US graphics sheets (menu/HUD + file-select)."
    )
    return relocation


def file_select_palette() -> Relocation:
    """Bank ``$27``: the file-select US palette overlay. Four CGRAM rows differ
    JP<->US; ``USFS_PaletteLoadForFileSelect`` runs the stock US load and then
    overlays those four US palettes (US-ROM ``PaletteData`` slices,
    ``incbin``\\ 'd from ``english/usfs_pal.bin``). ``file_select`` repoints
    the one ``JSL`` at it.
    """
    relocation = Relocation()
    relocation.place(
        """\
USFS_PaletteLoadForFileSelect:
    JSL PaletteLoadForFileSelect    ; stock US load (JP palette for FS rows)
    PHP                             ; preserve caller's processor mode (M/X)
    REP #$30                        ; 16-bit A AND index
    PHB
    PHK
    PLB
    LDX.w #$0000
.row5
    LDA.l USFS_Palette+$00,X
    STA.l $7EC3A2,X                 ; buffer A (compose)
    STA.l $7EC5A2,X                 ; buffer B (NMI DMA source)
    INX
    INX
    CPX.w #$000E
    BNE .row5
    LDX.w #$0000
.row7
    LDA.l USFS_Palette+$0E,X
    STA.l $7EC3E2,X
    STA.l $7EC5E2,X
    INX
    INX
    CPX.w #$000E
    BNE .row7
    LDX.w #$0000
.row9
    LDA.l USFS_Palette+$1C,X
    STA.l $7EC422,X
    STA.l $7EC622,X
    INX
    INX
    CPX.w #$000E
    BNE .row9
    LDX.w #$0000
.row11
    LDA.l USFS_Palette+$2A,X
    STA.l $7EC462,X
    STA.l $7EC662,X
    INX
    INX
    CPX.w #$000E
    BNE .row11
    LDA.w #$0000                    ; row 14 color 15 -> black (US)
    STA.l $7EC4DE
    STA.l $7EC6DE
    PLB
    PLP
    RTL

; Four US file-select palettes (colors 1-7 each), CGRAM-row order 5, 7, 9, 11.
USFS_Palette:
    incbin "english/usfs_pal.bin\"""",
        0x278000,
        "file-select US palette overlay + data.",
        namespace=False,
    )
    return relocation


def placements(
    *, changes: bool, usdasm: Path, jpdasm: Path
) -> list[Placement]:
    """Every subsystem's placed, ``EN_``-namespaced pieces, in one list."""
    relocations = [
        text(usdasm, changes=changes),
        font_upload(jpdasm, changes=changes),
        credits_bank(jpdasm, usdasm, changes=changes),
        item_menu(usdasm, jpdasm, changes=changes),
        file_select(usdasm, jpdasm, changes=changes),
        graphics(changes=changes),
        file_select_palette(),
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
        default=Path(),
        help="directory to write the bank_XX.asm files into",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    written = write_banks(
        placements(
            changes=not args.baseline, usdasm=args.usdasm, jpdasm=args.jpdasm
        ),
        args.out,
    )
    mode = "baseline" if args.baseline else "with changes"
    print(f"wrote {len(written)} banks ({mode}): {', '.join(written)}")


if __name__ == "__main__":
    main()
