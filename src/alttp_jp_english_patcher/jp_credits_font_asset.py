#!/usr/bin/env python3
"""The JP credits' bold font, decompressed offline into a plain flat 2bpp
tile sheet (see ``resources/binextract_jp_credits_font.py.template``).

JP 1.0 ships this font pre-compressed (a bespoke bit-packed scheme,
``DecompressFontGFX``/``BuildSomeTextMasks``, bank_0E) that the game
otherwise has to unpack at runtime before it can display credits at all.
Doing that same unpacking once, here, at generation/extraction time --
instead of shipping the compressed asset plus the routines that unpack it
into the ROM -- lets credits load its font exactly like the English dialogue
font already does (a plain ``incbin`` + flat VRAM upload), and needs none of
``BuildSomeTextMasks``/``DecompressFontGFX``/``TransferFontToVRAM``'s JP
originals at runtime at all.

The compressed source asset (``TextGFX``/``TextCharMasks``) covers JP's
*whole* font -- 512 glyphs, almost all kanji/kana that only JP's own native
(now unreachable) dialogue renderer ever read. This module only decompresses
the ~69 glyphs :data:`NEEDED_GLYPHS` (``Credits_CharacterToTile``, jpdasm
bank_0E, actually references -- the rest are left blank in the output. This
is not a size optimization on the *output* (still a flat 8192-byte sheet,
same layout `Credits_CharacterToTile`'s tile numbers already expect, so
nothing about its own indices has to change) -- it's simply not bothering to
decompress the ~86% of the font nothing in this build ever displays. The
original compressed asset is untouched either way: this project only hooks
in and adds, never deletes, so JP's own full font is still sitting in the
base ROM exactly where it always was.

Mirrors :mod:`us_assets`'s template-rendering shape, but for one JP-ROM-
derived, *computed* (not sliced) asset -- see that module's docstring for the
general pattern this follows.
"""

from __future__ import annotations

from importlib import resources
from string import Template

#: The JP 1.0 ROM this asset's extraction algorithm was verified against.
JP_ROM_MD5 = "03a63945398191337e896e5771f77173"

#: Filename under ``bin/gfx/`` (both the graft's incbin path and the
#: extractor's output path).
FILENAME = "jp_credits_font.2bpp"

#: 512 glyphs * 2 tiles (top+bottom half) * 16 bytes/tile -- the layout
#: Credits_CharacterToTile's own tile numbers expect; unrelated to how many
#: of those glyphs actually get decompressed (see NEEDED_GLYPHS).
SIZE = 8192

#: The TextCharMasks/TextGFX glyph indices Credits_CharacterToTile actually
#: references (derived from its own tile numbers -- each covers 2 flat
#: tiles, 16 slots apart, so a referenced tile can name either half of its
#: glyph). Every other glyph is skipped entirely; its output bytes stay 0.
NEEDED_GLYPHS: frozenset[int] = frozenset(
    {
        160,
        161,
        162,
        163,
        164,
        165,
        166,
        167,
        168,
        169,
        170,
        171,
        172,
        173,
        174,
        175,
        176,
        177,
        178,
        179,
        180,
        181,
        182,
        183,
        184,
        185,
        186,
        187,
        188,
        189,
        190,
        191,
        192,
        193,
        194,
        195,
        199,
        200,
        207,
        208,
        209,
        212,
        213,
        214,
        215,
        216,
        217,
        218,
        219,
        220,
        236,
        237,
        238,
        239,
        240,
        241,
        242,
        243,
        244,
        245,
        246,
        247,
        248,
        249,
        250,
        251,
        252,
        253,
        254,
    }
)

#: Expected md5 of the decompressed output -- verified against a live
#: capture of the same buffer from a real JP 1.0 boot (Mesen, dev-time only;
#: no emulator is used by the shipped extractor itself), restricted to the
#: tiles NEEDED_GLYPHS actually populates.
OUTPUT_MD5 = "e51762fd76fcda1fb0ab9f16da5809a0"


def _load_template() -> Template:
    """The ``binextract-jp-credits-font.py`` source template -- a bundled
    package resource (``.py.template``, so its name makes clear it is not
    itself runnable Python), filled in by
    :func:`render_binextract_jp_credits_font`.
    """
    text = (
        resources.files("alttp_jp_english_patcher")
        .joinpath("resources", "binextract_jp_credits_font.py.template")
        .read_text(encoding="utf-8")
    )
    return Template(text)


def render_binextract_jp_credits_font() -> str:
    """The full source of ``binextract-jp-credits-font.py``, generated from
    this module's constants -- the deployed extractor and :data:`OUTPUT_MD5`
    can never disagree, since both come from here.
    """
    needed = ", ".join(str(g) for g in sorted(NEEDED_GLYPHS))
    return _load_template().substitute(
        jp_rom_md5=repr(JP_ROM_MD5),
        output_md5=repr(OUTPUT_MD5),
        needed_glyphs=f"frozenset({{{needed}}})",
    )
