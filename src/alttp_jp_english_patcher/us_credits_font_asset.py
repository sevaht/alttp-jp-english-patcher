#!/usr/bin/env python3
"""A US-styled alternate for the credits' font, in the same tile-slot layout
as :mod:`jp_credits_font_asset`'s ``jp_credits_font.2bpp`` (see
``resources/binextract_us_credits_font.py.template``).

Every character JP 1.0's credits actually display (``Credits_CharacterToTile``,
jpdasm bank_0E -- each entry pre-labeled with its literal character by the
disassembler, no reverse-engineering needed there) is looked up by its US
dialogue-font (``TheFont``) tile instead of JP's own bold glyph, written to
the SAME tile slot ``jp_credits_font.2bpp`` uses for that character. This
lets credits load either file interchangeably (``--credits-font jp/us``)
with no other code changes -- same slot numbers, same
``Credits_CharacterToTile``/``CreditsTextLine`` data, just different pixel
data at each slot.

:data:`TILE_MAP` (JP credits tile slot -> source US ``TheFont`` tile) was
derived from two ``usdasm`` bank_0E facts, both confirmed by reading the
source directly (not guessed): the VWF renderer's own character-code ->
``TheFont`` tile arithmetic (``RenderText_PerformVWFing``: ``tile = ((code &
$F0) << 1) | (code & $0F)``), and its ``.width`` table's own row-by-row
comments giving each character's code (A-Z = 0-25, 0-9 = 52-61, the
``!?-.,…`` row = 62-67, the ``"↑↓←→'`` row = 76-81). The one credits
character with no US dialogue-font equivalent (a green bullet/list-marker,
``•``, used once) is left out of the map entirely -- its slot stays blank
(0x00) in the output, same as any slot no JP credits text references at all.

Mirrors :mod:`jp_credits_font_asset`'s template-rendering shape.
"""

from __future__ import annotations

from importlib import resources
from string import Template

from .us_assets import US_ROM_MD5, asset

#: Filename under ``bin/gfx/`` (both the graft's incbin path and the
#: extractor's output path).
FILENAME = "us_credits_font.2bpp"

#: Same layout/size as jp_credits_font.2bpp -- one 8192-byte flat sheet.
SIZE = 8192

#: Expected md5 of the built output.
OUTPUT_MD5 = "219a3c464df4472cb070c843575abb6e"

#: (JP credits tile slot -> source US TheFont tile), one entry per character
#: JP's credits actually reference. A slot not listed here is left blank.
TILE_MAP: dict[int, int] = {
    320: 100,
    321: 101,
    322: 102,
    323: 103,
    324: 104,
    325: 105,
    326: 106,
    327: 107,
    328: 108,
    329: 109,
    330: 0,
    331: 1,
    332: 2,
    333: 3,
    334: 4,
    335: 5,
    336: 100,
    337: 101,
    338: 102,
    339: 103,
    340: 104,
    341: 105,
    342: 106,
    343: 107,
    344: 108,
    345: 109,
    346: 0,
    347: 1,
    348: 2,
    349: 3,
    350: 4,
    351: 5,
    352: 6,
    353: 7,
    354: 8,
    355: 9,
    356: 10,
    357: 11,
    358: 12,
    359: 13,
    360: 14,
    361: 15,
    362: 32,
    363: 33,
    364: 34,
    365: 35,
    366: 36,
    367: 37,
    368: 6,
    369: 7,
    370: 8,
    371: 9,
    372: 10,
    373: 11,
    374: 12,
    375: 13,
    376: 14,
    377: 15,
    378: 32,
    379: 33,
    380: 34,
    381: 35,
    382: 36,
    383: 37,
    384: 38,
    385: 39,
    386: 40,
    387: 41,
    391: 110,
    400: 38,
    401: 39,
    402: 40,
    403: 41,
    407: 110,
    415: 0,
    424: 161,
    425: 130,
    432: 1,
    433: 2,
    436: 3,
    437: 4,
    438: 5,
    439: 6,
    440: 161,
    441: 161,
    442: 128,
    443: 129,
    476: 7,
    477: 8,
    478: 9,
    479: 10,
    496: 11,
    497: 12,
    498: 13,
    499: 14,
    500: 15,
    501: 32,
    502: 33,
    503: 34,
    504: 35,
    505: 36,
    506: 37,
    507: 38,
    508: 39,
    509: 40,
    510: 41,
}


def _load_template() -> Template:
    """The ``binextract-us-credits-font.py`` source template -- a bundled
    package resource (``.py.template``, so its name makes clear it is not
    itself runnable Python), filled in by
    :func:`render_binextract_us_credits_font`.
    """
    text = (
        resources.files("alttp_jp_english_patcher")
        .joinpath("resources", "binextract_us_credits_font.py.template")
        .read_text(encoding="utf-8")
    )
    return Template(text)


def render_binextract_us_credits_font() -> str:
    """The full source of ``binextract-us-credits-font.py``, generated from
    this module's constants -- the deployed extractor and :data:`OUTPUT_MD5`
    can never disagree, since both come from here. Reads US ``TheFont``'s
    own ROM slice directly (:func:`us_assets.asset`'s ``us_font.2bpp``
    offsets), not the already-extracted file, so extraction order between
    scripts is never a dependency.
    """
    font_asset = asset("us_font.2bpp")
    (font_slice,) = font_asset.slices
    tile_map_lines = "\n".join(
        f"    {slot}: {tile}," for slot, tile in sorted(TILE_MAP.items())
    )
    return _load_template().substitute(
        us_rom_md5=repr(US_ROM_MD5),
        output_md5=repr(OUTPUT_MD5),
        us_font_offset=hex(font_slice.offset),
        us_font_size=hex(font_slice.length),
        tile_map="{\n" + tile_map_lines + "\n}",
    )
