#!/usr/bin/env python3
"""Generate ``english/us_text.asm`` -- the US text subsystem, relocated into
the expanded English ROM and renamed into the ``EN_`` namespace.

WHAT WE PULL  (verbatim from ../usdasm, the US disassembly, by name)
-------------------------------------------------------------------
* The text ENGINE -- ``Assembly.extract`` starts from the routines we actually
  need (``ENGINE_ROOTS``) and recursively follows every reference, so the whole
  live subsystem comes along without us listing it. Dead ``UNREACHABLE_``/
  ``NULL_`` blocks drop out, and their space is reserved with an ``org`` so the
  survivors keep their address.
* The MESSAGE data -- ``Message_Data`` (US ``text.asm``, bank ``$1C``) up to
  its free ROM, plus its ``bank_0E`` overflow ``Message_DataExtra``.

ADDRESSES  (we compute them ourselves -- no assembler)
------------------------------------------------------
Each source line already carries a ``#_AAAAAA:`` anchor, and the gap to the
next anchor is its byte size. The extracted ``Assembly`` keeps those sizes, so
after any line edit it re-emits the ``#_`` anchors by tracking the PC from the
target ``org``. Every edit below is byte-neutral, so mirror-placed code
(engine -> ``$2E``) lands at US address ``+$200000`` exactly -- no cascade; the
message data sits in free banks ``$22``/``$23``.

TWO OUTPUTS  (``--baseline`` selects which)
-------------------------------------------
* default (with changes): the shipping form -- our graft edits applied, each
  hook given its bare JP name so unmodified callers resolve here, and the two
  override stubs emitted.
* ``--baseline``: the same US code relocated and ``EN_``-namespaced but with
  *none* of our changes and *no* bare hook aliases/stubs. Committing this
  first, then the default, isolates a clean diff of exactly what we changed.

OUR CHANGES TO THE STOCK US CODE  (skipped by ``--baseline``)
------------------------------------------------------------
1. 4-character names -- JP saves hold 4 name chars, US 6: clamp the two
   ``[NAME]`` readers to 4 and drop the 2 unused field slots (``DEX DEX``),
   replacing the two cut copy-writes with ``NOP`` fill so the routine keeps the
   stock US byte length.
2. Message-ID realignment with JP -- drop US-only messages ``000B``/``000C``
   (so game-code message IDs match JP), then re-append those two cursor-prompt
   messages at the next free IDs ``$018B``/``$018C`` and repoint the engine
   there.
3. Re-caption the stock ``RenderText_FilterName`` -- names now arrive as
   US-native character codes (entered on the US file-select screen).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from snes_assembly_parser import Assembly, data, datas, instructions, notes

from graft import Relocation, mirror, substitute

if TYPE_CHECKING:
    from snes_assembly_parser import Line

USDASM = Path("../usdasm")  # default US disassembly (override with --usdasm)
OUT = Path("us_text.asm")
RULE = ";" + "-" * 99

# ---- WHAT WE PULL ---------------------------------------------------------
# The engine's two endpoints plus TextCommandLengths, which the engine reaches
# only by an out-of-bounds table index (see ENGINE_GAP_NOTES) so no reference
# discovers it. Recursion from these three names pulls the whole live engine.
ENGINE_ROOTS = ("RenderText", "CreateMessagePointers", "TextCommandLengths")
# JP entry points we repoint here: each hook keeps its bare name (so unmodified
# JP callers land on our version) alongside its EN_ name.
ENGINE_HOOKS = frozenset(
    {"RenderText", "Module0E_02_RenderText", "CreateMessagePointers"}
)
# Globals shared with bank_00 (left un-namespaced): our font, referenced by the
# engine and uploaded by bank_00's TransferFontToVRAM.
SHARED = frozenset({"TheFont", "TheFont_end"})
ENGINE_GAP_NOTES = {
    "UNREACHABLE_0ED3CF": (
        "CreateMessagePointers over-reads "
        "RenderText_MoreInitialSettings,Y up to index $7F (past its "
        "20-byte end) across this pad into TextCommandLengths just "
        "below, so this offset is load-bearing."
    )
}

# ---- WHERE IT LANDS (English ROM, 2nd MB) ---------------------------------
FONT_ORG = 0x208000
MESSAGE_MAIN_ORG = 0x228000
MESSAGE_OVERFLOW_ORG = 0x238000
DECOMPRESS_HOOK = 0x0EF572  # JP DecompressFontGFX
MASKS_HOOK = 0x0EFCB2  # JP BuildSomeTextMasks

# (3) The stock US RenderText_FilterName's snarky comment, re-captioned to
# explain why we keep it verbatim (multi-line, so applied to the rendered
# text).
FILTER_NAME_OLD = "; I hate this thing..."
FILTER_NAME_NEW = "\n".join(  # noqa: FLY002
    [
        "; [ENG-NAME] Names are entered on the US file-select screen, so they",
        "; store native US character codes. This is the stock US",
        "; RenderText_FilterName (maps name-entry codes to VWF glyph codes,",
        "; I/i and '!' special cases + the lowercase-encode branch).",
    ]
)


def edit_engine(engine: Assembly) -> None:
    """Apply the 4-char-name and message-ID graft edits, as line operations.

    Inserted instructions are sized by :func:`instructions` (computed from the
    opcode), so no hand-written byte count is needed.
    """
    # (1) [NAME] field: JP names are 4 chars; the stock US handler is 6 wide.
    # Read and filter only 4 (US reads 6), copy the 4 real slots (unchanged,
    # below), then drop the 2 unused field slots (DEX DEX) and trim to the real
    # width. Crucially we replace the two slot-5/6 copy writes with DEX DEX +
    # NOP ($EA) fill of the SAME 12 bytes, so the routine stays byte-identical
    # in length to stock US and nothing downstream shifts (no cascade -- vs the
    # old approach that inserted a 6-byte pad). The 2 dropped slots never
    # render: the field advances only 4, so the next parsed byte / message
    # terminator overwrites them.
    engine.replace(
        "CPY.w #$0006", "CPY.w #$0004", count=2
    )  # read + filter loops
    engine.replace(
        "LDY.w #$0005", "LDY.w #$0003", count=1
    )  # trim the 4 real slots
    engine.delete(
        "LDA.b $0C", ";---"
    )  # cut the two slot-5/6 copy writes (12 bytes)
    engine.insert_after(
        "STA.l $7F11FD,X",
        notes(
            [
                "",
                "; [ENG-FS] The 4 real name slots are copied above; drop the",
                "; 2 unused slots of the 6-wide US [NAME] field (DEX DEX) so",
                "; the trim rewinds to the real width. The db is NOP ($EA)",
                "; fill, keeping this routine the same length as stock US, in",
                "; place of the two cut copy writes, so nothing downstream",
                "; shifts.",
            ]
        )
        + instructions(["DEX", "DEX"])
        + [data("db $EA, $EA, $EA, $EA, $EA, $EA, $EA, $EA, $EA, $EA")],
    )
    engine.annotate(
        "ADC.w #$0006",
        "[ENG-FS] advance by the US 6-wide field; DEX DEX below trims to 4",
    )
    engine.annotate(
        "LDY.w #$0003",
        "[ENG-FS] trim trailing spaces across the 4-char [NAME] field",
    )
    # (2) repoint RenderText_Choose2HighOr3's cursor prompts to the re-appended
    # copies
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
    """(2) The two Choose2High cursor prompts, re-appended past JP's ID range,
    terminated by $FF (the marker CreateMessagePointers scans for)."""
    return [
        *notes(
            [
                RULE.replace("-", "="),
                "; [ENG-TEXT] Restored Choose2High cursor-prompt messages (US",
                "; Message_000B/000C). The ID realignment drops US-only",
                "; 000B/000C so message IDs match JP, but the US engine's",
                "; RenderText_Choose2HighOr3 references them by ID for the",
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


# Our VWF text font (font.2bpp); read by the engine and the bank_00 upload.
THE_FONT = 'TheFont:\n    incbin "english/font.2bpp"\nTheFont_end:'


def decompress_stub() -> str:
    """Override for JP's DecompressFontGFX: the US font needs no decompression,
    so this hook just tail-calls the plain-2bpp uploader."""
    return (
        "; [ENG-FSFONT] JP's DecompressFontGFX VWF-rendered the JP font into "
        "$7E2000; the US ROM has no\n"
        "; such routine -- its text font is the plain 2bpp TheFont, uploaded "
        "to VRAM $E000 by\n"
        "; TransferFontToVRAM. So this override is just a tail-call.\n"
        "DecompressFontGFX:\n"
        "EN_DecompressFontGFX:\n"
        f"#_{mirror(DECOMPRESS_HOOK):06X}: JML EN_TransferFontToVRAM       "
        "; upload TheFont, then RTL"
    )


def masks_stub() -> str:
    """Override for JP's BuildSomeTextMasks: a no-op here (masks come from the
    PerformVWFing tables), kept so JP callers land somewhere valid."""
    return (
        "; [ENG-TEXT] BuildSomeTextMasks is a no-op here (masks come from the "
        "PerformVWFing tables);\n"
        "; keep the hook so its JP callers land somewhere valid.\n"
        "BuildSomeTextMasks:\n"
        "EN_BuildSomeTextMasks:\n"
        f"#_{mirror(MASKS_HOOK):06X}: RTL"
    )


def require_start(segment: Assembly, what: str) -> int:
    """The segment's first anchor address, or a loud failure."""
    start = segment.start_address
    if start is None:
        msg = f"{what} has no address anchor"
        raise ValueError(msg)
    return start


def build(*, changes: bool, usdasm: Path = USDASM) -> Relocation:
    bank_0e = Assembly.from_path(usdasm / "bank_0E.asm")
    text_asm = Assembly.from_path(usdasm / "text.asm")

    # ---- ENGINE: pull the whole live subsystem from ENGINE_ROOTS by refs.
    engine = bank_0e.extract(
        ENGINE_ROOTS,
        recursive=True,
        external=SHARED,
        comments=True,
        gap_notes=ENGINE_GAP_NOTES,
    )
    if changes:
        edit_engine(engine)
    engine_org = mirror(require_start(engine, "engine"))  # $0EC440 -> $2EC440

    # ---- MESSAGES: main table (bank $1C, to its free ROM) + bank_0E overflow.
    main = text_asm.blocks_until("Message_Data")
    overflow = text_asm.blocks_until("Message_DataExtra")
    if changes:
        main.delete_block("Message_000B")  # drop US-only cursor messages,
        main.delete_block("Message_000C")  # so game-code message IDs match JP
        overflow.append(cursor_messages())  # re-appended past JP's ID range

    # The engine re-caption is a multi-line comment swap -- done on the
    # engine's rendered text (placed as a str), one of the few pieces that is
    # not a plain Assembly. One global EN_ namespace keeps cross-block refs
    # (engine <-> data) in step; the bare hook aliases and override stubs are
    # part of the graft, so a baseline build emits neither.
    engine_text = engine.render(engine_org)
    if changes:
        engine_text = substitute(engine_text, FILTER_NAME_OLD, FILTER_NAME_NEW)

    overflow_note = "MESSAGE overflow (US bank_0E)"
    overflow_note += " + re-appended cursor prompts." if changes else "."

    relocation = Relocation(
        header(changes=changes),
        hooks=ENGINE_HOOKS if changes else frozenset(),
        shared=SHARED,
    )
    relocation.place(
        THE_FONT,
        FONT_ORG,
        "Our VWF text font (font.2bpp); read by the bank_00 upload.",
        namespace=False,  # raw blob; TheFont/TheFont_end stay bare (shared)
    )
    relocation.place(
        engine_text,
        engine_org,
        "Text ENGINE, mirror-placed from US bank_0E $0EC440.",
    )
    if changes:
        # The override stubs are hand-written in final form (their own bare
        # hook alias + EN_ name), so they are emitted verbatim.
        relocation.place(
            decompress_stub(),
            mirror(DECOMPRESS_HOOK),
            "Hook: DecompressFontGFX (mirror of JP $0EF572).",
            namespace=False,
        )
        relocation.place(
            masks_stub(),
            mirror(MASKS_HOOK),
            "Hook: BuildSomeTextMasks (mirror of JP $0EFCB2).",
            namespace=False,
        )
    relocation.place(
        main,
        MESSAGE_MAIN_ORG,
        "MESSAGE data (US text.asm bank $1C); free bank.",
    )
    relocation.place(overflow, MESSAGE_OVERFLOW_ORG, overflow_note)
    return relocation


def header(*, changes: bool) -> str:
    head = (
        "; ==== US English text subsystem, relocated to the expanded ROM "
        "(2nd MB) ====\n"
        "; generated by english/generate_us_text.py from ../usdasm. "
        "Do not hand-edit."
    )
    if not changes:
        head += (
            "\n; BASELINE build (--baseline): the relocated US code with none "
            "of our graft changes,\n; no bare hook aliases, and no override "
            "stubs -- the clean base for a change diff."
        )
    return head


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="emit the relocated US code with none of our graft changes "
        "(no edits, hook aliases, or stubs) -- the clean base for a diff",
    )
    parser.add_argument(
        "--usdasm",
        type=Path,
        default=USDASM,
        help=f"US disassembly to pull from (default: {USDASM})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT,
        help=f"where to write us_text.asm (default: {OUT})",
    )
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        build(changes=not args.baseline, usdasm=args.usdasm).render()
    )
    mode = "baseline" if args.baseline else "with changes"
    print(f"wrote {args.out} ({mode})")


if __name__ == "__main__":
    main()
