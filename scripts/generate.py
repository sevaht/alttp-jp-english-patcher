#!/usr/bin/env python3
"""Generate the whole English program: one :class:`Rom` loaded, edited, saved.

:func:`build` loads the pristine JP disassembly as a single whole-program
:class:`~snes_assembly_parser.Rom` and does everything on it: it
:meth:`~Rom.add`\\ s each relocated subsystem (built below as a
:class:`graft.Relocation` -- its placed, ``EN_``-namespaced pieces, each
knowing the ``org`` it lands at), :func:`hooks <apply_base_edits>` the base
banks to reach those copies *by name or ``#_`` address anchor* (never by which
file a routine lives in), and wires ``main.asm``. :meth:`~Rom.write` then emits
the entire fork: the base banks hooked in place, the graft grouped into
``bank_20`` .. ``bank_2E`` beside them (see :func:`graft.bank_header`), and
every untouched unit round-tripped byte-for-byte.

The relocated code is pulled *by name* from the US/JP disassembly
(``../usdasm``, ``../jpdasm``); the binary assets (font, graphics, palette) are
US-ROM byte slices ``incbin``\\ 'd from ``english/`` (via
``extract_english_assets.py``).
Each subsystem is self-contained -- its constants, helpers, and edits live in
its own function -- so there is nothing file-wide to trace through.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from snes_assembly_parser import (
    Assembly,
    Block,
    Edit,
    LandingPad,
    Line,
    Pool,
    Rom,
    data,
    datas,
    dbr_trampolines,
    instructions,
    note,
    notes,
)

from graft import Relocation, bank_header, mirror, require_start, substitute

USDASM = Path("../usdasm")
JPDASM = Path("../jpdasm")


@dataclass(frozen=True)
class Sources:
    """The two input disassemblies the graft pulls from, bundled so each
    subsystem takes one argument instead of two in an easy-to-swap order."""

    us: Rom
    jp: Rom


# A landing-pad block's header comment: the real routines live a bank away, the
# freed JP entry-point names stay here and forward with a JSL/RTS bridge.
_REDIRECT_HEADER = (
    "; [ENG-REDIRECT] Landing pads: the real routines run in bank ${bank} "
    "(english/{file}).",
    "; They keep the JP entry-point names so unmodified same-bank JSR callers "
    "land here and",
    "; forward across the bank with a register-transparent JSL/RTS bridge (an "
    "argument in",
    "; A/X/Y passes straight through); the JP originals are preserved "
    "above as UNREACHABLE_*.",
)


def _redirect(bank: str, file: str) -> tuple[str, ...]:
    return tuple(
        line.format(bank=bank, file=file) for line in _REDIRECT_HEADER
    )


# The VWF font blob's labels, shared by the text engine and the bank_00 upload;
# left un-namespaced so both reach the same ``TheFont``.
THEFONT_LABELS = frozenset({"TheFont", "TheFont_end"})


def text(
    sources: Sources, *, changes: bool, extended_names: bool
) -> Relocation:
    """The US text subsystem: the VWF font (bank ``$20``), the message engine
    (mirror-placed to ``$2E``), and the message data (``$22``/``$23``).

    The engine is pulled whole by reference: the two endpoints plus
    ``TextCommandLengths`` (reached only by an out-of-bounds index) close over
    the entire live subsystem. Dead blocks drop out, their space held with an
    ``org`` so survivors keep their +$200000 mirror address.
    """
    us, jp = sources.us, sources.jp
    engine = us.extract(
        ("RenderText", "CreateMessagePointers", "TextCommandLengths"),
        recursive=True,
        external=THEFONT_LABELS,
        comments=True,
        gap_notes={
            "UNREACHABLE_0ED3CF": (
                "CreateMessagePointers over-reads "
                "RenderText_MoreInitialSettings,Y up to index $7F (past its "
                "20-byte end) across this pad into TextCommandLengths just "
                "below, so this offset is load-bearing."
            )
        },
    )
    main = us.blocks_until("Message_Data")
    overflow = us.blocks_until("Message_DataExtra")
    decompress_hook = jp.address_of("DecompressFontGFX")
    masks_hook = jp.address_of("BuildSomeTextMasks")

    if changes:
        # (1) [NAME] field: 6-char (extended) vs the legacy 4-char build.
        if extended_names:
            # The name is a 6-word field at $3D5 (widened -- see file_select),
            # so the stock US 6-char handler works; just repoint its read.
            name_field: list[Edit] = [
                ("LDA.l $7003D9,X", "LDA.l $7003D5,X", 1)
            ]
        else:
            # Narrow the US 6-char handler to JP's 4-char field at $3D9: read/
            # filter/copy 4, then DEX DEX + $EA fill (byte-neutral) for slots
            # 5-6.
            def narrow_to_four(engine: Assembly) -> None:
                engine.replace("CPY.w #$0006", "CPY.w #$0004", count=2)
                engine.replace("LDY.w #$0005", "LDY.w #$0003", count=1)
                engine.splice(
                    "LDA.b $0C",
                    [
                        *instructions(["DEX", "DEX"]),
                        data("db " + ", ".join(["$EA"] * 10)),
                    ],
                    until=";---",
                )

            name_field = [narrow_to_four]
        # (2) repoints RenderText_Choose2HighOr3's two cursor prompts to the
        # copies re-appended below.
        engine_edits: dict[str, list[Edit]] = {
            "ParseText_WritePlayerName": name_field,
            "RenderText_Choose2HighOr3": [
                (
                    "dw $000B",
                    "dw $018B    ; [ENG-TEXT] was $000B ->"
                    " Message_Choose2High_opt1",
                    1,
                ),
                (
                    "dw $000C",
                    "dw $018C    ; [ENG-TEXT] was $000C ->"
                    " Message_Choose2High_opt2",
                    1,
                ),
            ],
        }
        engine.apply_edit_table(engine_edits)
        # (3) message IDs: drop US-only 000B/000C so IDs match JP, then
        # re-append those two Choose2High cursor prompts past JP's ID range
        # (395=$18B, 396=$18C), terminated by $FF (the marker
        # CreateMessagePointers scans for). The bytes ARE the US 000B/000C
        # blocks, pulled and relabelled -- not hand-transcribed.
        opt1 = main.block("Message_000B")
        opt1.replace(
            "Message_000B:",
            "Message_Choose2High_opt1:  ; ID $018B (395), cursor line 2",
            1,
        )
        opt2 = main.block("Message_000C")
        opt2.replace(
            "Message_000C:",
            "Message_Choose2High_opt2:  ; ID $018C (396), cursor line 3",
            1,
        )
        main.delete_block("Message_000B")
        main.delete_block("Message_000C")
        overflow.append(
            notes(
                [
                    ";" + "=" * 99,
                    "; [ENG-TEXT] Restored Choose2High cursor-prompt",
                    "; messages (US Message_000B/000C). The ID realign drops",
                    "; US-only 000B/000C so message IDs match JP, but the US",
                    "; engine's RenderText_Choose2HighOr3 references them by",
                    "; ID for the selection cursor. Re-appended at the next",
                    "; free IDs (past JP's 0-394). Without this a 2-option",
                    "; 'high' prompt (e.g. the Great Fairy upgrade) loaded",
                    "; whatever now sits at ID $000B as glitch text.",
                ]
            )
            + opt1.lines
            + notes([""])
            + opt2.lines
            + notes([""])
            + datas(
                [
                    "db $FF ; end of message table "
                    "(CreateMessagePointers terminator)"
                ]
            )
        )

    engine_org = mirror(require_start(engine))  # $0EC440 -> $2EC440
    engine_text = engine.render(engine_org)
    overflow_note = "MESSAGE overflow (US bank_0E)" + (
        " + re-appended cursor prompts." if changes else "."
    )

    # Every JP name this subsystem intercepts (freed in the base): the first
    # three claim a bare alias in the relocated engine; the last two are the
    # override stubs below (verbatim, already carrying a bare alias). None have
    # a same-bank caller, so all resolve to aliases (no pad).
    relocation = Relocation(
        hooked=(
            "RenderText",
            "Module0E_02_RenderText",
            "CreateMessagePointers",
            "DecompressFontGFX",
            "BuildSomeTextMasks",
        ),
        shared=THEFONT_LABELS,
        changes=changes,
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
        main, 0x228000, "MESSAGE data (US text.asm bank $1C); free bank."
    )
    relocation.place(overflow, 0x238000, overflow_note)
    if changes:
        # Re-caption the name filter (a multi-line comment swap on the rendered
        # engine text), then the two override stubs -- hand-written in final
        # form (own bare hook alias + EN_ name), emitted verbatim.
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
            f"Hook: DecompressFontGFX (mirror of JP ${decompress_hook:06X}).",
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
            f"Hook: BuildSomeTextMasks (mirror of JP ${masks_hook:06X}).",
            namespace=False,
        )
    relocation.place(
        engine_text,
        engine_org,
        "Text ENGINE, mirror-placed from US bank_0E $0EC440.",
    )
    return relocation


def font_upload(sources: Sources, *, changes: bool) -> Relocation:
    """Bank ``$20``: JP ``TransferFontToVRAM``, mirror-placed and repointed to
    upload our plain-2bpp ``TheFont`` to VRAM $E000 (was a $7E2000 VWF buffer).
    """
    jp = sources.jp
    root = "TransferFontToVRAM"
    routine = jp.extract([root], recursive=True, external=THEFONT_LABELS)
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
        hooked=(root,), shared=THEFONT_LABELS, changes=changes
    )
    relocation.place_mirror(
        routine, "bank-$00 TransferFontToVRAM (mirror of JP $00E596)."
    )
    return relocation


def credits_bank(sources: Sources, *, changes: bool) -> Relocation:
    """Bank ``$2E``: the JP credits reader + tables, mirror-placed, with the
    glyph map swapped to the US table so credits render in the US Latin font.

    Placed in three contiguous groups (JP interleaves them with credits code we
    do not relocate). The readers return long -- they are reached across banks
    via bank_0E landing pads -- and keep only their EN_ names (the bare aliases
    live under the pads in bank_0E), so no hooks/shared here.
    """
    us, jp = sources.us, sources.jp

    @dataclass(frozen=True)
    class Region:
        """One contiguous credits run, mirror-placed as a unit. ``us_glyphs``
        are the leading glyph->tile tables whose ``dw`` values are re-pointed
        at the US font (swapped from the identically-named US block/pool, same
        length so byte-neutral); ``jp_kept`` are the text/code/data members
        left as JP. Placed in order: glyph tables first, then kept."""

        us_glyphs: tuple[Block | Pool, ...]
        jp_kept: tuple[Block | Pool, ...]

        @property
        def members(self) -> tuple[Block | Pool, ...]:
            return (*self.us_glyphs, *self.jp_kept)

    regions = (
        Region(
            us_glyphs=(
                Block("Credits_CharacterToTile"),
                Block("CreditsBlankFillTile"),
            ),
            jp_kept=(Pool("CreditsTextLine"),),
        ),
        Region(
            # the pool holds the glyph .digits (swapped) then data offsets that
            # match US, so the whole pool re-points byte-neutrally.
            us_glyphs=(Pool("Credits_AddNextAttribution"),),
            jp_kept=(Block("Credits_AddNextAttribution"),),
        ),
        Region(
            us_glyphs=(),  # ending-sequence tilemap keeps JP palette attrs
            jp_kept=(
                Pool("Credits_AddEndingSequenceText"),
                Block("Credits_AddEndingSequenceText"),
            ),
        ),
    )
    readers = ("Credits_AddNextAttribution", "Credits_AddEndingSequenceText")

    # The readers are the hooks: a same-bank caller in bank_0E's credits driver
    # (not relocated) reaches them, so caller-analysis gives each a landing pad
    # in bank_0E's freed ROM.
    relocation = Relocation(
        hooked=readers,
        carried=frozenset(
            member.name for region in regions for member in region.members
        ),
        pad_region="NULL_0EEDFB",
        pad_header=_redirect("2E", "en_credits.asm"),
        changes=changes,
    )
    for region in regions:
        group = jp.concat(list(region.members))
        if changes:
            if region.us_glyphs:
                group.overlay_dw(us.concat(list(region.us_glyphs)).dw_rows())
            if any(member.name in readers for member in region.members):
                group.return_long()
        start = require_start(group)
        relocation.place(
            group, mirror(start), f"credits region, mirror of JP ${start:06X}."
        )
    return relocation


def item_menu(sources: Sources, *, changes: bool) -> Relocation:
    """Bank ``$2D``: the US item menu, mirror-placed. Four entry routines get a
    DBR-setting trampoline (their bodies become ``<name>_body`` and return
    long);
    the name-text tables get the US content, with the 2-row US ``Mirror`` table
    duplicated to JP's 4-row slot (cascading the rest forward $20 bytes).
    """
    us, jp = sources.us, sources.jp
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

    # The four entries are the hooks. Their same-bank JSR callers (the item-
    # menu dispatch) stay in bank_0D, so caller-analysis gives each a landing
    # pad in bank_0D's freed ROM (the bare name -> a DBR trampoline here). The
    # relocated blocks (bodies + name-text + cursor) are what moves along.
    relocation = Relocation(
        hooked=entries,
        carried=frozenset(
            [us_name for us_name, _, _ in bodies]
            + [*name_text, "MenuCursorPositions"]
        ),
        pad_region="NULL_0DAFDD",
        pad_header=_redirect("2D", "en_item_menu.asm"),
        changes=changes,
    )

    def place(body: Assembly, org: int) -> None:
        relocation.place(body, org, f"item-menu @ ${org:06X}.")

    if changes:
        place(dbr_trampolines(entries), 0x2DE100)
    for us_name, en_name, long_return in bodies:
        body = us.block(us_name, comments=False)
        if changes and long_return:
            body.return_long(restore_bank=True)  # PLB before RTL (DBR restore)
        if en_name != us_name:
            body.lines[0].label = en_name  # rename the routine label
        place(body, mirror(require_start(body)))

    def duplicate_mirror_rows(region: Assembly) -> None:
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
        for copy, src in zip(copies, rows, strict=True):
            copy.size = src.size
        region.lines[end:end] = copies

    def restore_ability_jp_rows(region: Assembly) -> None:
        # Rows 10-11 of AbilityText keep the JP tile values (not US).
        jp_rows = [
            line.arguments
            for line in jp.block("AbilityText", comments=False).lines
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

    region = us.concat([*name_text])
    if changes:
        region.apply_edit_table(
            {
                "ItemMenuNameText_Mirror": [duplicate_mirror_rows],
                "AbilityText": [restore_ability_jp_rows],
            }
        )
    place(region, mirror(require_start(region)))

    cursor = us.block("MenuCursorPositions", comments=False)
    # Cursor positions follow the Mirror table, which grew by $20 (2 rows).
    place(cursor, mirror(require_start(cursor)) + (0x20 if changes else 0))
    return relocation


def file_select(
    sources: Sources, *, changes: bool, extended_names: bool
) -> Relocation:
    """Bank ``$2C``: the US file-select / copy / erase / name-entry, packed
    contiguously from ``$2C8000`` (two JP-restored save routines are too big
    for
    their US slots to mirror-place). Pulled whole by recursion from the entry
    points; a few come from JP for the dual-save backup the US dropped.
    """
    us, jp = sources.us, sources.jp
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

    def build_irq_handler() -> Assembly:
        # The name-entry V-IRQ raster split, derived from JP
        # NoIRQThread's .not_mode7 sublabel: bank_00 keeps the IRQ-active check
        # (LDA $0128 / BEQ .IRQ_inactive) and JMLs here for the split (see
        # apply_base_edits); we JML back to .IRQ_inactive ($00821B). JP already
        # loads the #$38 split; we only add the name-entry ($0128 == $01) case
        # that loads #$74 instead, reusing JP's #$38 as the default.
        irq = jp.block("NoIRQThread").subblock(".not_mode7")
        # bank_00 keeps the active-check; replace it with our entry label.
        irq.splice(
            ".not_mode7",
            [
                "; [ENG-FS] Name-entry V-IRQ raster split (JP",
                "; NoIRQThread.not_mode7 + the $0128 name-entry case).",
                "IRQActiveHandler:",
            ],
            until="LDA.w TIMEUP",
        )
        irq.insert_before(
            "LDA.b #$38",
            [
                *instructions(
                    [
                        "LDA.w $0128",
                        "CMP.b #$01",
                        "BNE .default_split",
                        "LDA.b #$74",
                        "BRA .store_split",
                    ]
                ),
                ".default_split",
            ],
        )
        irq.insert_after("LDA.b #$38", [".store_split"])
        irq.append(instructions(["JML $00821B"]))
        return irq

    def edit_initialize_gfx(block: Assembly) -> None:
        # JP FileSelect_InitializeGFX -> English (name-banner + BG3 setup).
        block.delete("STZ.w $0AB6", until="JSL PaletteLoad_UnderworldSet")
        block.insert_after(
            "STA.w $0AA9",
            instructions(["LDA.b #$06", "STA.w $0AB6", "STA.w $0710"]),
        )
        block.delete("LDA.b #$01", until="STA.w $0AB2")
        block.insert_after(
            "JSL PaletteLoad_OWBG3", instructions(["LDA.b #$00"])
        )
        block.insert_after(
            "STA.w $0AA1", instructions(["LDA.b #$51", "STA.w $0AA2"])
        )

    def edit_erase(block: Assembly) -> None:
        # JP NameFile_EraseSave -> English blank fill + flags.
        block.delete("STZ.w $0B10", until="STZ.w $0B15")
        block.insert_after("STA.w $0128", instructions(["STZ.w $0B10"]))
        block.replace("LDA.b #$3E", "LDA.b #$83", count=1)
        block.replace("LDA.w #$019C", "LDA.w #$01F0", count=1)
        block.replace("LDA.w #$018C", "LDA.w #$00A9", count=1)
        if extended_names:
            # widen: prepend two blank-writes so all 6 words ($3D5-$3DF) clear.
            block.insert_before(
                "STA.l $7003D9,X",
                instructions(["STA.l $7003D5,X", "STA.l $7003D7,X"]),
            )
        # else JP's native four blank-writes at $3D9 match the 4-char field.

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

    # Player-name width fork. EXTENDED widens the SRAM name to a contiguous
    # 6-word field at $3D5 (ending just before the JP checksum marker at $3E1),
    # so the US 6-char-native routines just need their base repointed -4
    # ($7003D9 -> $7003D5). LEGACY keeps JP's 4-word field at $3D9 and narrows
    # the US routines to 4. Either way FileSelect_HandleInput/DrawDeaths touch
    # only post-name data (SCHKSM $3E1, deaths $401), so they are unchanged.
    if extended_names:
        shift = ("LDA.l $7003D9,X", "LDA.l $7003D5,X", 1)
        name_edits: dict[str, list[Edit]] = {
            "CopyFile_SelectionAndBlinker": [shift],
            "CopyFile_TargetSelectionAndBlink": [shift],
            "FileSelect_CopyNameToStripes": [shift],
            "NameFile_DrawSelectedCharacter": [shift],
            # the char write + the terminator read -- both $7003D9,X.
            "NameFile_DoTheNaming": [("$7003D9", "$7003D5", 2)],
            # the special-name cheat check (name-word 1 -> mushroom + items).
            "InitializeSaveFile": [("LDA.l $7003D9", "LDA.l $7003D5", 1)],
        }
    else:
        narrow = ("LDA.w #$0006", "LDA.w #$0004", 1)
        name_edits = {
            "CopyFile_SelectionAndBlinker": [narrow],
            "CopyFile_TargetSelectionAndBlink": [narrow],
            "FileSelect_CopyNameToStripes": [narrow],
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
                edit_name_player_tilemap,
            ],
        }
    edits: dict[str, list[Edit]] = {
        "FileSelect_HandleInput": [("LDA.l $7003E5,X", "LDA.l $7003E1,X", 1)],
        "FileSelect_DrawDeaths": [("LDA.l $700405,X", "LDA.l $700401,X", 1)],
        "ReinitializeFileSelectGraphics": [
            (
                "JSL PaletteLoadForFileSelect",
                "JSL USFS_PaletteLoadForFileSelect",
                1,
            )
        ],
        "FileSelect_InitializeGFX": [edit_initialize_gfx],
        "NameFile_EraseSave": [edit_erase],
        **name_edits,
    }

    # This subsystem is PACKED contiguously at $2C8000, not mirror-placed (two
    # JP save-backup routines are too big to mirror). Packing reassigns
    # absolute addresses, so blocks are emitted in US source order to keep the
    # few fall-through routines beside their successor.
    # Intro_SetStripesAndAdvance is a US #-label the single-unit closure cannot
    # reach, so it is named explicitly and pulled from US like the rest.
    reachable = us.closure(sorted(hooks), recursive=True)
    packed_blocks = list(
        dict.fromkeys(
            entry.name for entry in reachable if isinstance(entry, Block)
        )
    )
    if changes:
        packed_blocks += ["Intro_SetStripesAndAdvance"]

    lines = []
    for name in packed_blocks:
        # US/JP block (pool before routine) with its byte-neutral edits from
        # the table above applied.
        origin = jp if name in jp_blocks else us
        seg_lines = []
        if name in origin.pool_names:
            seg_lines += origin.pool(name, comments=False).lines
        seg_lines += origin.block(name, comments=False).lines
        segment = Assembly(seg_lines)
        if changes:
            segment.apply_edits(edits.get(name, []))
        lines += segment.lines
    if changes:  # IRQ handler built from a sublabel, not a top-level block
        lines += build_irq_handler().lines
    # The entry points are the hooks; the whole recursive closure is what
    # relocates, so the one same-bank caller (a BRL inside FileSelect_
    # HandleInput, itself relocated) moves along -> every hook is an alias.
    relocation = Relocation(
        hooked=tuple(sorted(hooks)),
        carried=frozenset(entry.name for entry in reachable),
        changes=changes,
    )
    relocation.place(Assembly(lines), 0x2C8000, "file-select, packed.")
    return relocation


def graphics(*, changes: bool) -> Relocation:
    """Bank ``$26``: the US menu/HUD + file-select graphics sheets (the
    kana/Latin font sheets ``GFX_DC``/``GFX_DD`` and the file-select "linoleum"
    background ``GFX_39``). Binary US-ROM slices, ``incbin``\\ 'd; each claims
    its freed JP name so the game's tables reach the US art.
    """
    # (JP sheet name, its US-ROM slice, extracted into english/). Packed from
    # $268000; referenced by symbol, so the exact address is asar's job.
    sheets = (
        ("GFX_DC", "gfx_dc.2bppc"),  # US menu / file-select font sheet ($69)
        ("GFX_DD", "gfx_dd.2bppc"),  # US menu / file-select font sheet ($6A)
        ("GFX_39", "gfx_39.3bppc"),  # US file-select "linoleum" bg ($39)
    )
    # Why each freed JP sheet is dead (annotates the base definition).
    dead_notes = {
        "GFX_39": (
            "; [ENG-GFX] JP menu-bg sheet $39 repointed at the US linoleum "
            "(GFX_39, usgfx.asm);",
            "; this JP data is no longer referenced.",
        ),
        "GFX_DC": (
            "; [ENG-GFX] JP menu-font sheet $69 repointed at the US font "
            "(GFX_DC, usgfx.asm).",
        ),
        "GFX_DD": (
            "; [ENG-GFX] JP $6A repointed at the US font (GFX_DD, usgfx.asm); "
            "data stays live via GFX_71.",
        ),
    }
    body = "\n\n".join(
        f'{name}:\n    incbin "english/{asset}"' for name, asset in sheets
    )
    relocation = Relocation(
        hooked=tuple(name for name, _ in sheets),
        hook_notes=dead_notes,
        changes=changes,
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
    the one ``JSL`` at it. Keeping all four palettes here (not filling JP's
    empty ``owanim_00`` in bank_1B) keeps every US palette in the graft and the
    base edit a pure repoint -- the shared ``PaletteLoadSingle`` reads bank $1B
    only, so a 2nd-MB copy is unreachable through the stock load anyway.

    NOTE on row 5: statically it looks unneeded -- the file-select drives
    ``PaletteLoad_UnderworldSet`` with ``$0AB6 = #$06`` (dungeon set $06, which
    is byte-identical US<->JP), and the overlaid slice ($1BD9AA) is in set $03.
    But dropping it was tested and turned the wooden file-select borders the
    wrong colour, so the runtime CGRAM ends up needing it after all -- the load
    path is more involved than the static read suggests. Keep all four rows.
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


# ---------------------------------------------------------------------------
# base-disassembly edits
# ---------------------------------------------------------------------------
# Reaching the relocated graft from the unmodified JP banks has two parts, both
# keyed *by name or #_ address anchor* through the whole-program Rom (never by
# which file a routine lives in, and failing loud on upstream drift):
#   * _wire_hooks -- the base half of every hook, DERIVED from the relocations
#     and the program's callers: free each hooked JP name, and decide per name
#     whether the relocated copy's bare alias suffices or a landing pad is
#     needed (a same-bank caller stays behind). Nothing to re-list here.
#   * apply_base_edits -- the few edits that are NOT a plain hook.
def _en_pad(name: str) -> LandingPad:
    """A landing pad forwarding the freed JP ``name`` to its ``EN_`` copy."""
    return LandingPad(name, f"EN_{name}")


def _wire_hooks(english: Rom, jp: Rom, relocations: list[Relocation]) -> None:
    """Wire the base half of every hook, deciding alias-vs-pad from callers.

    For each relocation: split its :attr:`~graft.Relocation.hooked` names into
    the ones a bare alias reaches (recorded back on the relocation as
    ``aliased``, for ``EN_`` namespacing) and the ones a same-bank caller
    strands (a landing pad in the relocation's ``pad_region``). Then free every
    hooked name in the base. Run *before* the relocations are added, so the
    alias set it records is the one their pieces emit.
    """
    for relocation in relocations:
        pad_names = tuple(
            name
            for name in relocation.hooked
            if jp.needs_landing_pad(name, relocated=relocation.carried)
        )
        relocation.aliased = frozenset(relocation.hooked) - frozenset(
            pad_names
        )
        for name in relocation.hooked:
            english.hook(name, comment=relocation.hook_notes.get(name, ()))
        if pad_names:
            if relocation.pad_region is None:
                msg = f"hooks {pad_names} need a pad but no pad_region is set"
                raise ValueError(msg)
            english.landing_pads(
                relocation.pad_region,
                [_en_pad(name) for name in pad_names],
                header=relocation.pad_header,
            )


def apply_base_edits(english: Rom) -> None:
    """Apply the base edits that are not plain hooks (see _wire_hooks)."""
    # V-IRQ active block -> the relocated name-entry raster-split handler.
    english.relocate_block(
        0x008205,
        "EN_IRQActiveHandler",
        resume=0x00820A,
        orphan=(0x38,),
        comment=(
            "; [ENG-FS] V-IRQ active block -> relocated handler in bank $2C "
            "(us_menu.asm).",
        ),
    )
    # Byte-neutral operand swaps: US BG3 blank tile, the US 126-tile text box,
    # and the three font-upload operands (-> our TheFont, uploaded to $E000).
    english.set_operand(
        0x008335,
        "LDA.w #$00A9",
        comment="[ENG-FS] US BG3 blank tile (was $0188 hex-pattern glyph)",
    )
    english.set_operand(
        0x008D02,
        "LDX.w #$07E0",
        comment="[ENG-TEXT] US 126-tile text box (was $0780 / 120)",
    )
    english.set_operand(0x00E557, "LDA.b #TheFont>>16")
    english.set_operand(0x00E563, "LDA.w #TheFont")
    english.set_operand(0x00E568, "LDX.w #(TheFont_end-TheFont)/2-1")
    # File-select: re-pin the FairyY data the relocation left behind, and keep
    # the one in-bank CopySaveToWRAM reference on the preserved JP original.
    english.insert_before("FileSelect_FairyY", ["org $0CCC67"])
    english.rewrite_reference(
        0x0CCE8B, "CopySaveToWRAM", "UNREACHABLE_CopySaveToWRAM"
    )


# ---------------------------------------------------------------------------
# main.asm: pull in the graft banks + pad the ROM to a clean 2 MB
# ---------------------------------------------------------------------------
_MAIN_ANCHOR = 'incsrc "bank_1F.asm"'
_MAIN_MARKER = 'incsrc "bank_20.asm"'
# Inserted right after the last base-bank include: the graft-bank includes,
# then the 2 MB padding + SNES header size byte the expansion needs (so the
# checksum is a plain byte-sum every emulator agrees on).
_MAIN_BLOCK = (
    "",
    'incsrc "bank_20.asm"',  # our VWF font + relocated TransferFontToVRAM
    'incsrc "bank_22.asm"',  # message data (main table)
    'incsrc "bank_23.asm"',  # message data (overflow)
    'incsrc "bank_26.asm"',  # US menu/HUD + file-select font & bg graphics
    'incsrc "bank_27.asm"',  # file-select US palette overlay + palette data
    'incsrc "bank_2C.asm"',  # file-select / copy / erase / name-entry
    'incsrc "bank_2D.asm"',  # item menu
    'incsrc "bank_2E.asm"',  # text engine (+ override stubs) and credits
    "",
    "; [ENG-FS] Pad the ROM up to a clean 2 MB (power-of-2). The English graft"
    " expands the ROM",
    "; into banks $20-$2E, leaving it at a non-power-of-2 size (~0x150000)."
    " The SNES header",
    "; checksum for a non-power-of-2 ROM is computed by a mirror-and-sum"
    " algorithm that asar and",
    "; some emulators (e.g. snes9x) disagree on, which made snes9x report"
    ' "invalid checksum".',
    "; Padding to exactly 2 MB makes the checksum a plain byte-sum that"
    " everyone agrees on, so",
    "; --fix-checksum writes a value snes9x accepts. The gaps between the"
    " graft banks ($21, $24-$25,",
    "; $28-$2B, $2F-$3F) are unused ($00 fill) -- valid LoROM space in a 2 MB"
    " ROM, free for future use.",
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


def patch_main_asm(english: Rom) -> None:
    """Wire the graft-bank includes + 2 MB padding into the entry ``main.asm``.

    Idempotent and located by the ``incsrc "bank_1F.asm"`` anchor, not a line
    number, so it survives upstream reformatting and fails loud if the anchor
    is gone.
    """
    if not english.order:
        msg = "patch_main_asm: Rom has no entry file"
        raise ValueError(msg)
    main = english.units[
        english.order[0]
    ]  # the entry (main.asm), loaded first
    if any(str(line).strip() == _MAIN_MARKER for line in main.lines):
        return
    anchor = next(
        (
            index
            for index, line in enumerate(main.lines)
            if str(line).strip() == _MAIN_ANCHOR
        ),
        None,
    )
    if anchor is None:
        msg = f"main.asm: anchor {_MAIN_ANCHOR!r} not found"
        raise ValueError(msg)
    main.lines[anchor + 1 : anchor + 1] = [
        Line.from_line(text) for text in _MAIN_BLOCK
    ]
    main.resize()


def build(
    *, usdasm: Path, jpdasm: Path, changes: bool, extended_names: bool = True
) -> Rom:
    """Assemble the whole English program as one editable :class:`Rom`.

    Loads the pristine US and JP disassemblies as whole-program
    :class:`Rom`\\ s, copies the JP into the working ``english`` program, then
    does everything on those objects -- the subsystems pull their code *by
    name* from ``us``/``jp`` (never by which bank file it lives in) and fold
    into ``english``, the base banks are hooked to reach them (unless
    ``changes`` is off, the change-free baseline), and ``main.asm`` is wired.
    Writing it back out -- base banks hooked in place, graft banks beside them
    -- is the caller's :meth:`Rom.write`. ``extended_names`` builds 6-character
    player names (the default); ``False`` is the legacy 4-character build.
    """
    sources = Sources(
        us=Rom.load(usdasm / "main.asm"), jp=Rom.load(jpdasm / "main.asm")
    )
    english = sources.jp.copy()
    relocations = [
        text(sources, changes=changes, extended_names=extended_names),
        font_upload(sources, changes=changes),
        credits_bank(sources, changes=changes),
        item_menu(sources, changes=changes),
        file_select(sources, changes=changes, extended_names=extended_names),
        graphics(changes=changes),
        file_select_palette(),
    ]
    # Wire hooks first: it classifies each hook (alias vs pad) from the
    # pristine JP's callers and records the alias set the pieces then emit.
    if changes:
        _wire_hooks(english, sources.jp, relocations)
    for relocation in relocations:
        english.add(relocation)
    if changes:
        apply_base_edits(english)  # the few edits that are not plain hooks
    patch_main_asm(english)
    return english


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="emit the change-free baseline (no graft edits or base hooks)",
    )
    parser.add_argument(
        "--no-extended-names",
        action="store_true",
        help="legacy 4-character player names (default: 6-character names)",
    )
    parser.add_argument("--usdasm", type=Path, default=USDASM)
    parser.add_argument("--jpdasm", type=Path, default=JPDASM)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(),
        help="jpdasm fork to write the whole English program into",
    )
    args = parser.parse_args()
    english = build(
        usdasm=args.usdasm,
        jpdasm=args.jpdasm,
        changes=not args.baseline,
        extended_names=not args.no_extended_names,
    )
    generated = english.write(args.out, bank_header=bank_header)
    mode = "baseline" if args.baseline else "with changes"
    print(
        f"wrote English program ({mode}): "
        f"{len(generated)} graft banks + base banks -> {args.out}"
    )


if __name__ == "__main__":
    main()
