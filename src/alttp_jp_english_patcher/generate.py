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

The relocated code is pulled *by name* from the US/JP disassembly; the binary
assets (font, graphics, palette) are US-ROM byte slices ``incbin``\\ 'd from
``bin/gfx/`` (alongside the base disassembly's own binaries there; regenerated
on the target by ``binextract-us.py``, see :mod:`us_assets`). Each subsystem
is self-contained -- its constants, helpers, and edits live in its own
function -- so there is nothing file-wide to trace through.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from . import us_assets
from .graft import Relocation, bank_header, mirror, require_start, substitute
from .snes_assembly_parser import (
    DEFAULT_ROW_WIDTH,
    Assembly,
    Block,
    Edit,
    LandingPad,
    Line,
    Pool,
    Rom,
    datas,
    dbr_trampolines,
    free_space,
    incbin_line,
    instructions,
    note,
    notes,
)

USDASM = Path("../usdasm")
JPDASM = Path("../jpdasm")

#: Rom.write()'s default null_padbyte_threshold: a free-ROM gap over this many
#: bytes is filled with a single padbyte/pad jump instead of explicit db $FF
#: rows. 0 disables padbyte entirely (always explicit rows).
DEFAULT_NULL_PADBYTE_THRESHOLD = 128

#: nop_fill()'s default threshold: a JMP-past-a-gap's *interior* dead bytes
#: over this many bytes are filled with padbyte/pad instead of one NOP per
#: byte. Distinct from DEFAULT_NULL_PADBYTE_THRESHOLD (and much smaller) since
#: these gaps are a single edit site's byte-neutral filler, not a whole
#: free-ROM region -- most are tiny. 0 disables padbyte entirely (always
#: explicit NOPs).
DEFAULT_NOP_PADBYTE_THRESHOLD = 64


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


def _resource_lines(filename: str) -> list[str]:
    """A hand-written 65816 package resource (``resources/<filename>``), read
    verbatim as lines. Label namespacing / placement is the caller's job."""
    text = (
        resources.files("alttp_jp_english_patcher")
        .joinpath("resources", filename)
        .read_text(encoding="utf-8")
    )
    return text.splitlines()


# In-place save migrator (packed into the file-select bank, invoked at boot):
# US and vanilla-Japanese save slots are converted to our 6-word-name-at-$3D5
# format so they load and play.
def _save_migration_lines() -> list[str]:
    return _resource_lines("save_migration.asm")


# Module04_NameFile submodule 4: names an already-valid, blank-named save
# (an unconvertible JP import) without erasing it -- see edit_check_blank_name
# and StampNewFileTag.
def _name_fix_lines() -> list[str]:
    return _resource_lines("name_fix.asm")


def _row_fill(directive: str, value: str, count: int) -> list[Line]:
    """``count`` copies of ``value`` under ``directive`` (``db``/``dw``),
    wrapped at :data:`~.snes_assembly_parser.DEFAULT_ROW_WIDTH` per line --
    the same width :func:`~.snes_assembly_parser.free_space`'s own explicit
    rows use, so a hand-built filler row (one this codebase constructs
    itself, rather than one sized/anchored from a parsed disassembly) reads
    the same way."""
    values = [value] * count
    return datas(
        f"{directive} " + ", ".join(values[i : i + DEFAULT_ROW_WIDTH])
        for i in range(0, count, DEFAULT_ROW_WIDTH)
    )


def nop_fill(
    count: int,
    tag: str,
    comment: str,
    *,
    nop_padbyte_threshold: int = DEFAULT_NOP_PADBYTE_THRESHOLD,
) -> list[Line]:
    """Baseline stand-in for a full-only insertion: same byte count, so an
    edited routine's size -- and every anchor after it -- matches the full
    build exactly.

    A wall of one ``NOP`` per byte reads worse the bigger ``count`` gets, so
    only 1 byte stays a lone ``NOP``; anything bigger jumps past the gap, then
    fills it: a single ``db`` row of ``$EA`` at or under
    ``nop_padbyte_threshold``, else ``fillbyte``/``fill`` -- mirroring
    ``free_space``'s own small-gap-explicit / large-gap-padbyte split, just at
    a much smaller default cutoff, since these gaps are one edit site's
    filler, not a whole free-ROM region (``nop_padbyte_threshold <= 0``
    disables that, same as ``free_space``'s ``null_padbyte_threshold``).
    Either way the dead bytes read as harmless NOPs on the off chance they are
    ever reached.

    The "jump past the gap" is ``BRA +0``/``BRL +gap`` -- asar's *literal*
    relative-displacement syntax (``BRA +0`` assembles straight to
    ``$80 $00``, ``BRL +5`` to ``$82 $05 $00``) -- rather than the
    mnemonic with a label marking where the gap ends: this code hasn't been
    placed yet when ``nop_fill`` runs -- often not even in its final bank
    (:func:`text`, for one, mirrors its engine into bank ``$2E`` after this
    runs) -- so there's no real address for a label to carry, and a
    same-purpose invented label (with nothing else to call it) is a name to
    collide, a scope to get wrong, and one more thing to read. A branch's
    displacement is just "how far to the next byte after the gap", which is
    ``0``/``gap`` -- known upfront in Python -- so ``+gap`` needs neither a
    label nor a real address; asar resolves it as a literal offset, not an
    address expression. Likewise ``fill`` (unlike ``pad``) takes a byte
    *count*, not a target address, so the large-gap branch does not need one
    either (and sidesteps a separate asar bug: ``pad``'s target silently
    mis-evaluates to a bogus address when given a forward-referenced label).
    """
    header = notes([f"; [{tag}] {comment}"])
    if count <= 1:
        return header + (instructions(["NOP"]) if count else [])
    if count == 2:  # noqa: PLR2004 -- BRA +0 (2-byte NOP), nothing to fill
        return [*header, *instructions(["BRA +0"])]
    gap = count - 3
    lines = [*header, *instructions([f"BRL +{gap}"])]
    if gap == 1:
        lines += instructions(["NOP"])
    elif gap > 1:
        if nop_padbyte_threshold > 0 and gap > nop_padbyte_threshold:
            fill_line = note(f"fill {gap}")
            fill_line.size = gap
            lines += [note("fillbyte $EA"), fill_line]
        else:
            lines += _row_fill("db", "$EA", gap)
    return lines


# The VWF font blob's labels, shared by the text engine and the bank_00 upload;
# left un-namespaced so both reach the same ``TheFont``.
THEFONT_LABELS = frozenset({"TheFont", "TheFont_end"})


def text(
    sources: Sources,
    *,
    changes: bool,
    nop_padbyte_threshold: int = DEFAULT_NOP_PADBYTE_THRESHOLD,
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
    # CreateMessagePointers walks byte-by-byte until it reads a literal $FF
    # (the table-end marker); in the US ROM this falls out for free since
    # Message_DataExtra runs to the natural, $FF-padded end of its bank. Our
    # relocated copy is pulled as just its own block (no trailing bank
    # padding), and the free ROM after it in bank $23 is $00-filled -- so
    # without an explicit terminator here, the scan runs past the real data
    # and never finds $FF (in practice: an effectively endless loop at boot,
    # since CreateMessagePointers runs once at startup). Needed
    # unconditionally -- both the baseline and the full build carry the
    # vanilla-preserved engine.
    overflow.append(
        datas(
            [
                "db $FF ; end of message table"
                " (CreateMessagePointers terminator)"
            ]
        )
    )
    decompress_hook = jp.address_of("DecompressFontGFX")
    masks_hook = jp.address_of("BuildSomeTextMasks")

    # (2) message-ID realignment, done in the ENGINE instead of the data. The
    # US has two messages JP lacks -- the Choose2High cursor prompts at IDs
    # $0B/$0C -- so every later message's US ID is JP's + 2. Rather than
    # delete them (which physically moves every byte of the data, exploding
    # the bank_22/bank_23 diff), teach CreateMessagePointers to hand those two
    # the out-of-range IDs $18B/$18C as it assigns IDs, so every real message
    # keeps its JP ID while the data stays byte-for-byte the US layout. Only
    # RenderText_Choose2HighOr3 references the two (repointed below,
    # full-only); without the redirect a 2-option "high" prompt (e.g. the
    # Great Fairy upgrade) would load whatever sits at ID $0B.
    #
    # Applied UNCONDITIONALLY, self-branching on `changes` at each site (real
    # redirect vs. same-size NOP filler in baseline), so CreateMessagePointers
    # is byte-neutral between baseline and full -- no cascade into RenderText
    # or the rest of the engine.
    if changes:
        engine.insert_after(
            "#_0ED3F9:",  # LDX #$0000 -- the table-index / ID-counter init
            instructions(
                [
                    "LDA.w #$0002 ; [ENG-TEXT] US-only msgs to give high IDs",
                    "STA.b $04    ; ($0B/$0C: the Choose2High cursor prompts)",
                    "LDA.w #$04A1 ; first high slot -> ID $18B ($18B * 3)",
                    "STA.b $06",
                ]
            ),
        )
    else:
        engine.insert_after(
            "#_0ED3F9:",
            nop_fill(
                10,
                "ENG-TEXT",
                "reserved: see CreateMessagePointers init",
                nop_padbyte_threshold=nop_padbyte_threshold,
            ),
        )
    if changes:
        engine.insert_before(
            "#_0ED3FC:",  # the per-message store, right past .next_message
            [
                *instructions(
                    [
                        "CPX.w #$0021 ; [ENG-TEXT] slot for ID $0B, where the",
                        "BNE .store   ; two US-only prompts fall...",
                        "LDA.b $04    ; ...divert them to $18B/$18C, then let",
                        "BEQ .store   ; the real msg $0B take this slot",
                        "PHX",
                        "LDX.b $06        ; the $18B/$18C table slot",
                        "LDA.b $00",
                        "STA.l $7F71C0,X",
                        "LDA.b $01",
                        "STA.l $7F71C1,X",
                        "PLX              ; keep the real ID index put",
                        "LDA.b $06",
                        "CLC",
                        "ADC.w #$0003     ; next high slot",
                        "STA.b $06",
                        "DEC.b $04",
                        "BRA .next_byte   ; walk msg; don't consume an ID",
                    ]
                ),
                Line.from_line(".store"),
            ],
        )
    else:
        engine.insert_before(
            "#_0ED3FC:",
            nop_fill(
                37,
                "ENG-TEXT",
                "reserved: see CreateMessagePointers check",
                nop_padbyte_threshold=nop_padbyte_threshold,
            ),
        )

    if changes:
        # (1) [NAME] field: the name is a 6-word field at $3D5 (widened -- see
        # file_select), so the stock US 6-char handler works; just repoint its
        # read.
        name_field: list[Edit] = [("LDA.l $7003D9,X", "LDA.l $7003D5,X", 1)]
        # (3) repoint RenderText_Choose2HighOr3's two cursor prompts to the
        # high IDs the engine now assigns them.
        engine_edits: dict[str, list[Edit]] = {
            "ParseText_WritePlayerName": name_field,
            "RenderText_Choose2HighOr3": [
                (
                    "dw $000B",
                    "dw $018B    ; [ENG-TEXT] cursor prompt 1"
                    " (see CreateMessagePointers)",
                    1,
                ),
                ("dw $000C", "dw $018C    ; [ENG-TEXT] cursor prompt 2", 1),
            ],
        }
        engine.apply_edit_table(engine_edits)
    engine.ensure_anchors()  # anchor the hand-written lines (either build)

    engine_org = mirror(require_start(engine))  # $0EC440 -> $2EC440
    engine_text = engine.render(engine_org)
    overflow_note = "MESSAGE overflow (US bank_0E)."

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
    # Our VWF text font (us_font.2bpp); a raw blob (TheFont/TheFont_end stay
    # bare, shared), read by the engine and the bank_00 upload.
    relocation.place(
        Assembly(
            [
                note("TheFont:"),
                incbin_line(
                    "bin/gfx/us_font.2bpp",
                    us_assets.asset("us_font.2bpp").size,
                ),
                note("TheFont_end:"),
            ]
        ),
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
            "; TransferFontToVRAM. No decompression needed.\n"
            "DecompressFontGFX:\n"
            "EN_DecompressFontGFX:\n"
            f"#_{mirror(decompress_hook):06X}: RTL ; US isn't compressed",
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
    """Bank ``$2D``: the US item menu, mirror-placed. Four entry routines get
    a DBR-setting trampoline (their bodies become ``<name>_body`` and return
    long); the name-text tables get the US content, with the 2-row US
    ``Mirror`` table filling JP's 4-row slot -- reserved in BOTH builds
    (real copies in full, same-size labelled padding in the baseline) so the
    tables after it -- and ``MenuCursorPositions`` (always ``+$20``) -- keep a
    stable address and don't cascade in the baseline<->full review diff.
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

    def expand_mirror_slot(region: Assembly) -> None:
        # US ItemMenuNameText_Mirror is 2 dw rows; JP's slot wants 4. Fill the
        # extra 2-row ($20) span in BOTH builds -- the real US rows duplicated
        # (full), or same-size labelled padding (baseline) -- so the tables
        # after Mirror (and MenuCursorPositions) keep their +$20 slot in either
        # build and never cascade in the review diff.
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
        if changes:
            fill = [Line.from_line(str(row)) for row in rows]
            for copy, src in zip(fill, rows, strict=True):
                copy.size = src.size
        else:
            fill = notes(
                [
                    "; [ENG-ITEM] reserved: JP's Mirror slot is 4 rows (US",
                    "; has 2); the full build fills these with the copies.",
                ]
            )
            for row in rows:
                fill += _row_fill("dw", "$FFFF", row.size // 2)
        region.lines[end:end] = fill

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
    expand_mirror_slot(region)  # both builds: real copies (full) or padding
    if changes:
        region.apply_edit_table({"AbilityText": [restore_ability_jp_rows]})
    place(region, mirror(require_start(region)))

    cursor = us.block("MenuCursorPositions", comments=False)
    # Cursor positions follow the Mirror table, whose 4-row slot is reserved in
    # both builds, so the cursor always sits $20 past its US mirror.
    place(cursor, mirror(require_start(cursor)) + 0x20)
    return relocation


def file_select(
    sources: Sources,
    *,
    changes: bool,
    null_padbyte_threshold: int,
    nop_padbyte_threshold: int = DEFAULT_NOP_PADBYTE_THRESHOLD,
) -> Relocation:
    """Bank ``$2C``: the US file-select / copy / erase / name-entry. Pulled
    whole by recursion from the entry points; a few come from JP for the
    dual-save backup the US dropped. US-sourced routines are mirror-placed at
    their US address + $200000 (stable, recognisable addresses); the JP
    restorations -- too big for their US slots -- plus the IRQ handler and save
    migrator pack into the free bottom of the bank, all gaps labelled NULL_.
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
        # Each site is made byte-neutral between baseline/full (real edit vs.
        # same-size NOP filler in baseline) so this routine's size -- and thus
        # every later routine's address -- never depends on `changes`.
        if changes:
            block.delete("STZ.w $0AB6", until="JSL PaletteLoad_UnderworldSet")
            block.insert_after(
                "STA.w $0AA9",
                instructions(["LDA.b #$06", "STA.w $0AB6", "STA.w $0710"]),
            )
        else:
            # unedited site is 3 bytes; the full build's replacement is 8.
            block.insert_after(
                "STZ.w $0AB6",
                nop_fill(
                    5,
                    "ENG-FS",
                    "reserved: see FileSelect_InitializeGFX>0AB6",
                    nop_padbyte_threshold=nop_padbyte_threshold,
                ),
            )
        if changes:
            block.delete("LDA.b #$01", until="STA.w $0AB2")
            block.insert_after(
                "JSL PaletteLoad_OWBG3", instructions(["LDA.b #$00"])
            )
        # (already byte-neutral: LDA.b #$01 (2) -> LDA.b #$00 (2); no baseline
        # padding needed.)
        if changes:
            block.insert_after(
                "STA.w $0AA1", instructions(["LDA.b #$51", "STA.w $0AA2"])
            )
        else:
            block.insert_after(
                "STA.w $0AA1",
                nop_fill(
                    5,
                    "ENG-FS",
                    "reserved: see FileSelect_InitializeGFX>0AA1",
                    nop_padbyte_threshold=nop_padbyte_threshold,
                ),
            )

    def edit_erase(block: Assembly) -> None:
        # JP NameFile_EraseSave -> English blank fill + flags. Same
        # byte-neutral-between-builds treatment as edit_initialize_gfx.
        if changes:
            block.delete("STZ.w $0B10", until="STZ.w $0B15")
            block.insert_after("STA.w $0128", instructions(["STZ.w $0B10"]))
            block.replace("LDA.b #$3E", "LDA.b #$83", count=1)
            block.replace("LDA.w #$019C", "LDA.w #$01F0", count=1)
            block.replace("LDA.w #$018C", "LDA.w #$00A9", count=1)
        # (the STZ.w $0B10 move and the 3 replaces are already byte-neutral;
        # no baseline padding needed for any of them.)
        if changes:
            # widen: prepend two blank-writes so all 6 words ($3D5-$3DF) clear.
            block.insert_before(
                "STA.l $7003D9,X",
                instructions(["STA.l $7003D5,X", "STA.l $7003D7,X"]),
            )
        else:
            block.insert_before(
                "STA.l $7003D9,X",
                nop_fill(
                    8,
                    "ENG-FS",
                    "reserved: see NameFile_EraseSave>7003D9",
                    nop_padbyte_threshold=nop_padbyte_threshold,
                ),
            )

    def edit_widen_idle_exit(block: Assembly) -> None:
        # FileSelect_HandleInput's very first "no relevant input this frame"
        # check has to reach all the way to the routine's own .exit -- it was
        # already close to BEQ's +-127 limit in the unmodified US source, and
        # this routine's own growth here (edit_check_blank_name's real JSR or
        # its same-size baseline filler -- either way, both builds grow it
        # identically) tips it 1 byte over. Widen to an unconditional long
        # jump; applied unconditionally (not gated on `changes`) since both
        # builds need it equally.
        block.splice(
            "BEQ .exit",
            [*instructions(["BNE .not_idle", "JMP .exit"]), ".not_idle"],
        )

    def edit_check_blank_name(block: Assembly) -> None:
        # US FileSelect_HandleInput: a valid save ($BF,X != 0, about to fall
        # into the normal load-and-play path) whose name is all-blank (see
        # ConvertJP's blank fallback for an unconvertible JP import) needs a
        # name before it can be played. The actual check/redirect lives
        # out-of-line (FileSelect_NameIsBlankRedirect, name_fix.asm) so this
        # inline footprint is just a 3-byte JSR -- this routine's own
        # pre-existing short branches (BEQ/BRA to its ".exit") sit mid-routine,
        # before this insertion point, with little headroom to spare. Packed
        # low (see low_names) since it grows past its original
        # US slot -- byte-neutral between builds like FileSelect_InitializeGFX/
        # NameFile_EraseSave's edits, so a same-size filler stands in for the
        # baseline.
        if changes:
            block.insert_after(
                "BEQ .no_file_there",
                instructions(["JSR FileSelect_NameIsBlankRedirect"]),
            )
        else:
            block.insert_after(
                "BEQ .no_file_there",
                nop_fill(
                    3,
                    "ENG-FS",
                    "reserved: see FileSelect_HandleInput>blank-name check",
                    nop_padbyte_threshold=nop_padbyte_threshold,
                ),
            )

    def edit_add_rename_submodule(block: Assembly) -> None:
        # Append submodule 4 (NameFile_SetupRename, see name_fix.asm /
        # edit_check_blank_name) to the dispatch table. Module04_NameFile is
        # packed low (see low_names), so -- like edit_initialize_gfx/
        # edit_erase -- it needs the same size in both builds; a `dl` entry
        # is data, never executed as code, so the baseline stand-in is a
        # plain 3-byte placeholder rather than nop_fill (which is for
        # instruction-flow filler).
        if changes:
            block.insert_after(
                "dl NameFile_DoTheNaming", datas(["dl NameFile_SetupRename"])
            )
        else:
            block.insert_after(
                "dl NameFile_DoTheNaming",
                notes(["; [ENG-FS] reserved: unused submodule 4 slot"])
                + datas(["dl $000000"]),
            )

    def edit_handle_input_marker(block: Assembly) -> None:
        # US FileSelect_HandleInput reads the $3E5 marker natively; JP's is
        # $3E1. Same length either way, but gated (not a plain tuple) now
        # that this routine is packed low (see low_names) and so always
        # edited -- baseline should still read the untouched US marker,
        # matching edit_initialize_gfx/edit_erase's own already-byte-neutral
        # replaces, which are gated the same way.
        if changes:
            block.replace("LDA.l $7003E5,X", "LDA.l $7003E1,X", count=1)

    # Player name: widen the SRAM name to a contiguous 6-word field at $3D5
    # (ending just before the JP checksum marker at $3E1), so the US
    # 6-char-native routines just need their base repointed -4 ($7003D9 ->
    # $7003D5). FileSelect_HandleInput/DrawDeaths touch only post-name data
    # (SCHKSM $3E1, deaths $401), so they are unchanged.
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
    edits: dict[str, list[Edit]] = {
        "FileSelect_HandleInput": [
            edit_handle_input_marker,
            edit_check_blank_name,
            edit_widen_idle_exit,
        ],
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
        "Module04_NameFile": [edit_add_rename_submodule],
        **name_edits,
    }

    def edit_mark_checksum_only(block: Assembly) -> None:
        # A zero-byte, scope-transparent label marking InitializeSaveFile's
        # checksum-recompute tail (right before the `LDX.b $00` that reloads
        # the slot offset), so StampNewFileTag's rename-only branch below can
        # jump straight there. Anchored on the copy-loop's own exit branch
        # since `LDX.b $00` alone isn't unique in this routine (it also
        # appears right after the checksum loop).
        block.insert_after("BPL .copy_next", ["#checksum_only:"])

    # Save compatibility: migrate foreign slots to our format (skippable with
    # save_compat=False). The migrator (save_migration.asm resource) lands in
    # this bank; it is *invoked* at boot from bank_00 (see apply_base_edits) so
    # it runs before InitializeMemoryAndSRAM's $3E1 sanity zeroing.
    if changes:
        # Tag freshly-created files as ours -- byte-neutrally, so
        # InitializeSaveFile keeps its size and its US mirror slot. The $55AA
        # marker's own `STA.l $7003E1,X` (4 bytes) is swapped for a `JSL
        # StampNewFileTag` (also 4 bytes); the stub (built in the tail below)
        # writes the marker AND our $410 tag, then RTLs -- or, for a
        # blank-name rename (see edit_check_blank_name), skips straight to
        # the checksum recompute instead (edit_mark_checksum_only's label).
        edits["InitializeSaveFile"].append(
            ("STA.l $7003E1,X", "JSL StampNewFileTag", 1)
        )
        edits["InitializeSaveFile"].append(edit_mark_checksum_only)

    def stamp_new_file_stub() -> list[Line]:
        return (
            notes(
                [
                    ";" + "=" * 99,
                    "; [ENG-FS] New-file format tag, out-of-line so",
                    "; InitializeSaveFile stays byte-neutral (a JSL replaces",
                    "; its $55AA-marker STA -- same 4 bytes). A holds $55AA",
                    "; on entry. If the marker's already set, this save was",
                    "; never erased -- a blank-name rename, not a new file",
                    "; -- so skip the marker/bomb-wall/deaths/starting-items",
                    "; reset and jump straight to the checksum recompute.",
                    "StampNewFileTag:",
                ]
            )
            + instructions(
                [
                    "CMP.l $7003E1,X    ; already $55AA? (A is still $55AA)",
                    "BEQ .rename_only",
                    "STA.l $7003E1,X    ; the $55AA marker",
                    "LDA.w #$0006",
                    "STA.l $700410,X    ; our-format tag",
                    "RTL",
                ]
            )
            + notes([".rename_only"])
            + instructions(
                [
                    "TSC                 ; discard the JSL return address",
                    "CLC                 ; (3 bytes) so RTL doesn't land back",
                    "ADC.w #$0003        ; after this JSL -- we're jumping",
                    "TCS                 ; past it, to the checksum tail",
                    "JML checksum_only",
                ]
            )
        )

    # ---- placement: mirror the US routines, pack the JP restorations low ----
    # Bank $2C is the +$200000 mirror of US bank $0C, where every routine we
    # pull originates. US-sourced routines are MIRROR-placed at their US
    # address + $200000, so each keeps a stable, source-recognisable address
    # and a byte-neutral edit never renumbers its neighbours (a clean
    # baseline<->full diff). The JP restorations are BIGGER than the US slots
    # they'd occupy (that is why they were pulled), so they cannot sit in the
    # US layout; they -- plus the CopyFile_FindFileIndices stub that falls into
    # KILLFile_FindFileIndices, and the IRQ handler + save migrator -- pack
    # into the free bottom of the bank ($2C8000..). Every gap is a labelled
    # NULL_ free-ROM block (the disassembly convention we owe the expanded
    # banks).
    reachable = us.closure(sorted(hooks), recursive=True)
    carried = frozenset(entry.name for entry in reachable)
    packed_blocks = list(
        dict.fromkeys(
            entry.name for entry in reachable if isinstance(entry, Block)
        )
    )
    # Intro_SetStripesAndAdvance is a US #-label the closure cannot reach; the
    # relocated code JSRs it in every build (baseline included), so pull it
    # explicitly or the baseline has a dangling reference and won't assemble.
    packed_blocks += ["Intro_SetStripesAndAdvance"]

    # The routines that CANNOT mirror-place (JP restorations bigger than their
    # US slot). This is also the pack order; the CopyFile_FindFileIndices /
    # KILLFile_FindFileIndices pair must stay adjacent (the former sets A=$07
    # and falls straight into the latter).
    # InitializeSaveFile is NOT here: a short BNE in NameFile_DoTheNaming pins
    # it to the US layout, so it stays mirror-placed (it fits the US slot
    # exactly, and its tag edit is byte-neutral -- see StampNewFileTag).
    # FileSelect_HandleInput and Module04_NameFile are ALSO here now: neither
    # is branch-distance-pinned (FileSelect_HandleInput is only JSL'd;
    # Module04_NameFile is only reached via bank_00's RunModule data table),
    # and mirror-placing left zero slack before the next mirrored routine in
    # each case (CopySaveToWRAM sits byte-adjacent to FileSelect_HandleInput
    # in the source US ROM), so growing either one here (edit_check_blank_name/
    # edit_add_rename_submodule) would overlap the next mirrored routine.
    # Packing them low needs the same byte-neutral treatment as the other
    # low_names members.
    low_names = [
        "FileSelect_InitializeGFX",
        "CopyFile_FindFileIndices",
        "KILLFile_FindFileIndices",
        "NameFile_EraseSave",
        "FileSelect_HandleInput",
        "Module04_NameFile",
        "IntroLogoTilemap",
    ]
    low_set = frozenset(low_names)

    def pull(name: str, *, edited: bool) -> Assembly:
        # An asar pool is emitted inline just before its routine, so a pulled
        # segment is (pool + block) and its first byte is the pool's, not the
        # routine label's -- callers that need the placement address use
        # require_start(), not address_of().
        origin = jp if name in jp_blocks else us
        seg: list[Line] = []
        if name in origin.pool_names:
            seg += origin.pool(name, comments=False).lines
        seg += origin.block(name, comments=False).lines
        asm = Assembly(seg)
        if edited:
            asm.apply_edits(edits.get(name, []))
        return asm

    def width(asm: Assembly) -> int:
        return sum(line.size for line in asm.lines)

    # Packed low region, from the bank base.
    low_org = 0x2C8000
    low: list[Line] = []
    pc = low_org
    for name in low_names:
        # edited=True unconditionally: edit_initialize_gfx/edit_erase (the
        # only low_names entries with edits) branch on `changes` themselves
        # and pad the baseline to match the full build's size (see above), so
        # every build is already byte-neutral here -- no growth to absorb.
        body = pull(name, edited=True)
        low += body.lines
        pc += width(body)
    # NB: the IRQ handler + save migrator are appended AFTER the US region
    # (see `tail` below), not here -- keeping the low region (and thus the big
    # bridge NULL_) byte-identical between baseline and full.
    low_end = low_org + sum(line.size for line in low)

    # Routines mirror-placed at their US address + $200000, ascending order,
    # with a labelled NULL_ gap bridging the unpulled space between them. A
    # US-sourced segment keys on its own first byte (an inline pool precedes
    # the routine); a JP restoration kept here (InitializeSaveFile) takes its
    # US-equivalent slot instead of its own JP mirror.
    def us_place(name: str, seg: Assembly) -> int:
        if name in jp_blocks:
            return mirror(us.address_of(name))
        return mirror(require_start(seg))

    us_segs = [
        (us_place(name, seg), name, seg)
        for name in packed_blocks
        if name not in low_set
        for seg in [pull(name, edited=changes)]
    ]
    us_segs.sort(key=lambda item: item[0])
    us_region: list[Line] = []
    first_mirror = us_segs[0][0]
    pc = first_mirror
    for target, name, seg in us_segs:
        if target < pc:
            msg = f"file_select: US mirror overlap at {name}"
            raise ValueError(msg)
        if target > pc:
            us_region += free_space(
                pc, target - pc, null_padbyte_threshold=null_padbyte_threshold
            )
            pc = target
        us_region += seg.lines
        pc += width(seg)

    # New code JP has no home for: the name-entry IRQ handler and the save
    # migrator (both reached by label from bank_00). Appended after the US
    # region so their full-only presence never shifts the low region or the
    # mirrored routines -- it lands in the free tail instead.
    tail: list[Line] = []
    if changes:  # IRQ handler built from a sublabel, not a top-level block
        tail += build_irq_handler().lines
        tail += stamp_new_file_stub()  # InitializeSaveFile's byte-neutral tag
        # ensure_anchors gives the hand-written asm the #_<hex> per-line labels
        # the disassembly convention wants; render re-stamps them at emit time.
        tail += (
            Assembly.from_content(_save_migration_lines())
            .ensure_anchors()
            .lines
        )
        tail += Assembly.from_content(_name_fix_lines()).ensure_anchors().lines

    if first_mirror < low_end:
        msg = "file_select: low region overruns the US mirror start"
        raise ValueError(msg)
    bridge = free_space(
        low_end,
        first_mirror - low_end,
        null_padbyte_threshold=null_padbyte_threshold,
    )
    bank = low + bridge + us_region + tail

    relocation = Relocation(
        hooked=tuple(sorted(hooks)), carried=carried, changes=changes
    )
    relocation.place(
        Assembly(bank),
        low_org,
        "file-select: US routines mirror-placed; JP restorations packed low, "
        "IRQ handler + save migrator in the tail.",
    )
    return relocation


def graphics(*, changes: bool) -> Relocation:
    """Bank ``$26``: the US menu/HUD + file-select graphics sheets (the
    kana/Latin font sheets ``GFX_DC``/``GFX_DD`` and the file-select "linoleum"
    background ``GFX_39``). Binary US-ROM slices, ``incbin``\\ 'd; each claims
    its freed JP name so the game's tables reach the US art.
    """
    # (JP sheet name, its US-ROM slice under bin/gfx/). Packed from $268000;
    # referenced by symbol, so the exact address is asar's job.
    sheets = (
        ("GFX_DC", "us_gfx_dc.2bppc"),  # US menu/file-select font ($69)
        ("GFX_DD", "us_gfx_dd.2bppc"),  # US menu/file-select font ($6A)
        ("GFX_39", "us_gfx_39.3bppc"),  # US file-select "linoleum" bg ($39)
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
    lines: list[Line] = []
    for name, filename in sheets:
        lines.append(note(f"{name}:"))
        lines.append(
            incbin_line(f"bin/gfx/{filename}", us_assets.asset(filename).size)
        )
        lines.append(note(""))
    relocation = Relocation(
        hooked=tuple(name for name, _ in sheets),
        hook_notes=dead_notes,
        changes=changes,
    )
    relocation.place(
        Assembly(lines[:-1]),
        0x268000,
        "US graphics sheets (menu/HUD + file-select).",
    )
    return relocation


def file_select_palette(*, changes: bool) -> Relocation:
    """Bank ``$27``: the file-select US palette overlay. Four CGRAM rows differ
    JP<->US; ``USFS_PaletteLoadForFileSelect`` (our own routine, hand-written
    -- not sourced from either disassembly, so it is full-only; see
    ``resources/usfs_palette_load.asm``) runs the stock US load and then
    overlays those four US palettes from ``USFS_Palette`` (a plain US-ROM
    ``PaletteData`` byte slice, ``incbin``\\ 'd from ``bin/gfx/us_palette.bin``
    -- present in both builds, like the graft's other raw asset extractions).
    ``file_select`` repoints the one ``JSL`` at it. Keeping all four palettes
    here (not filling JP's empty ``owanim_00`` in bank_1B) keeps every US
    palette in the graft and the base edit a pure repoint -- the shared
    ``PaletteLoadSingle`` reads bank $1B only, so a 2nd-MB copy is unreachable
    through the stock load anyway.
    """
    relocation = Relocation(changes=changes)
    lines: list[Line] = []
    if changes:
        lines += (
            Assembly.from_content(_resource_lines("usfs_palette_load.asm"))
            .ensure_anchors()
            .lines
        )
        lines.append(note(""))
    lines += [
        note(
            "; Four US file-select palettes (colors 1-7 each), CGRAM-row"
            " order 5, 7, 9, 11."
        ),
        note("USFS_Palette:"),
        incbin_line(
            "bin/gfx/us_palette.bin", us_assets.asset("us_palette.bin").size
        ),
    ]
    relocation.place(
        Assembly(lines),
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
    # Save compatibility: invoke the migrator (in bank $2C) from bank_00's
    # InitializeMemoryAndSRAM, BEFORE it zeroes any main slot's $3E1 word whose
    # value isn't the $55AA marker. A US save's marker lives at $3E5, so its
    # $3E1 would be cleared (breaking the checksum) before the file-select
    # runs. The relocated stub migrates, replays the displaced LDA, JMLs back.
    english.relocate_block(
        0x0087EF,
        "EN_MigrateAtBoot",
        resume=0x0087F3,
        comment=(
            "; [ENG-FS] migrate foreign save slots before the $3E1 sanity "
            "check (us_menu.asm).",
        ),
    )
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
    # File-select: keep the one in-bank CopySaveToWRAM reference pointing at
    # the preserved JP original (which the graft leaves in place, unmoved -- so
    # no org re-pin is needed).
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
    *,
    usdasm: Path,
    jpdasm: Path,
    changes: bool,
    null_padbyte_threshold: int = DEFAULT_NULL_PADBYTE_THRESHOLD,
    nop_padbyte_threshold: int = DEFAULT_NOP_PADBYTE_THRESHOLD,
) -> Rom:
    """Assemble the whole English program as one editable :class:`Rom`.

    Loads the pristine US and JP disassemblies as whole-program
    :class:`Rom`\\ s, copies the JP into the working ``english`` program, then
    does everything on those objects -- the subsystems pull their code *by
    name* from ``us``/``jp`` (never by which bank file it lives in) and fold
    into ``english``, the base banks are hooked to reach them (unless
    ``changes`` is off, the change-free baseline), and ``main.asm`` is wired.
    Writing it back out -- base banks hooked in place, graft banks beside them
    -- is the caller's :meth:`Rom.write` (pass it the *same*
    ``null_padbyte_threshold``: this only covers a subsystem's own internal
    gaps, e.g. ``file_select``'s low-region/US-mirror bridge -- write()
    independently fills every *bank-level* gap). ``nop_padbyte_threshold`` is
    separate: it only governs the baseline's byte-neutral filler at a
    ``changes``-guarded edit site (see :func:`nop_fill`), never a bank-level
    free-ROM region. Player
    names are a 6-character field.
    """
    sources = Sources(
        us=Rom.load(usdasm / "main.asm"), jp=Rom.load(jpdasm / "main.asm")
    )
    english = sources.jp.copy()
    relocations = [
        text(
            sources,
            changes=changes,
            nop_padbyte_threshold=nop_padbyte_threshold,
        ),
        font_upload(sources, changes=changes),
        credits_bank(sources, changes=changes),
        item_menu(sources, changes=changes),
        file_select(
            sources,
            changes=changes,
            null_padbyte_threshold=null_padbyte_threshold,
            nop_padbyte_threshold=nop_padbyte_threshold,
        ),
        graphics(changes=changes),
        file_select_palette(changes=changes),
    ]
    # Wire hooks first: it classifies each hook (alias vs pad) from the
    # pristine JP's callers and records the alias set the pieces then emit.
    if changes:
        _wire_hooks(english, sources.jp, relocations)
    for relocation in relocations:
        english.add(relocation)
    if changes:
        apply_base_edits(english)
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
        "--no-save-compatibility",
        action="store_true",
        help="omit the on-entry US/Japanese save-slot migrator",
    )
    parser.add_argument("--usdasm", type=Path, default=USDASM)
    parser.add_argument("--jpdasm", type=Path, default=JPDASM)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(),
        help="jpdasm fork to write the whole English program into",
    )
    parser.add_argument(
        "--null-padbyte-threshold",
        type=int,
        default=DEFAULT_NULL_PADBYTE_THRESHOLD,
        help="free-ROM gaps over this many bytes use a padbyte/pad jump "
        f"instead of explicit db $FF rows; 0 disables padbyte entirely, "
        f"always explicit rows (default: {DEFAULT_NULL_PADBYTE_THRESHOLD})",
    )
    parser.add_argument(
        "--nop-padbyte-threshold",
        type=int,
        default=DEFAULT_NOP_PADBYTE_THRESHOLD,
        help="a baseline edit-site filler's interior dead bytes (past its "
        "JMP) over this many bytes use a padbyte/pad fill instead of one "
        "NOP per byte; 0 disables padbyte entirely, always explicit NOPs "
        f"(default: {DEFAULT_NOP_PADBYTE_THRESHOLD}). Separate from "
        "--null-padbyte-threshold, which only covers bank-level free-ROM "
        "regions",
    )
    args = parser.parse_args()
    english = build(
        usdasm=args.usdasm,
        jpdasm=args.jpdasm,
        changes=not args.baseline,
        null_padbyte_threshold=args.null_padbyte_threshold,
        nop_padbyte_threshold=args.nop_padbyte_threshold,
    )
    generated = english.write(
        args.out,
        bank_header=bank_header,
        null_padbyte_threshold=args.null_padbyte_threshold,
    )
    mode = "baseline" if args.baseline else "with changes"
    print(
        f"wrote English program ({mode}): "
        f"{len(generated)} graft banks + base banks -> {args.out}"
    )


if __name__ == "__main__":
    main()
