#!/usr/bin/env python3
"""The authoritative table of US-ROM-derived binary assets the graft
``incbin``\\ s.

Each entry's byte range(s) are the single source of truth for two things that
must never drift apart: :func:`~alttp_jp_english_patcher.generate.build`'s
``incbin`` sizing (an ``incbin``'d file's size can't be measured by our own
sizer -- it doesn't exist yet at generation time; the target runs
``binextract-us.py`` itself, later, as a separate step) and the extraction
script deployed to the target (:func:`render_binextract_us`), which cuts these
exact byte ranges out of the user's US ROM. Changing an offset/size here and
regenerating covers both -- there is nowhere else these numbers are written
down.

Assets live under ``bin/gfx/`` (matching the base disassembly's own binary
layout, e.g. ``bin/gfx/link.4bpp``) with a ``us_`` prefix marking their origin
alongside jpdasm's own JP-ROM-derived files in the same directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from string import Template

#: The US ROM this whole module's offsets/sizes/md5s were measured against.
US_ROM_MD5 = "608c22b8ff930c62dc2de54bcd6eba72"


@dataclass(frozen=True)
class Slice:
    """One contiguous US-ROM byte range (a plain file offset, not a mapped
    SNES address -- LoROM adds no bank-header padding, so they coincide for
    these single-bank slices, but the extractor reads the ROM file directly).
    """

    offset: int
    length: int


@dataclass(frozen=True)
class UsAsset:
    """One ``incbin``'d file: one or more US-ROM slices, concatenated."""

    #: Filename under ``bin/gfx/`` (both the graft's incbin path and the
    #: extractor's output path).
    filename: str
    slices: tuple[Slice, ...]
    #: Expected md5 of the concatenated slices -- the extractor stops loudly
    #: if a user's ROM doesn't produce this (wrong ROM revision/region).
    md5: str
    #: A short one-line description, reused as the extractor's inline comment.
    comment: str

    @property
    def size(self) -> int:
        """Total byte count -- what an ``incbin`` of this file sizes to."""
        return sum(s.length for s in self.slices)


US_ASSETS: tuple[UsAsset, ...] = (
    UsAsset(
        "us_font.2bpp",
        (Slice(0x70000, 0x1000),),
        "56d8e02353800ed7c095791a58556274",
        "US VWF font (plain ROM-offset byte slice)",
    ),
    UsAsset(
        "us_gfx_dc.2bppc",
        (Slice(0x0C2F0D, 0x613),),
        "1dc3ce334108dc118e481a84d8368b65",
        "US menu/file-select font sheet GFX_DC (compressed slice;"
        " $18AF0D LoROM)",
    ),
    UsAsset(
        "us_gfx_dd.2bppc",
        (Slice(0x0C3520, 0x433),),
        "e97ca7c5551d6de2ca7ca98effd99c81",
        "US menu/file-select font sheet GFX_DD (compressed slice;"
        " $18B520 LoROM)",
    ),
    UsAsset(
        "us_gfx_39.3bppc",
        (Slice(0x09C817, 0x351),),
        "c79da8a80348417038634560a9486110",
        'US file-select "linoleum" background GFX_39 (compressed slice;'
        " $13C817 LoROM)",
    ),
    UsAsset(
        "us_palette.bin",
        (
            Slice(0x0DD9AA, 14),  # PaletteData row 5 ($1BD9AA)
            Slice(0x0DE604, 14),  # PaletteData_owanim_00 row 7 ($1BE604)
            Slice(0x0DD218, 14),  # PaletteData row 9 ($1BD218)
            Slice(0x0DD254, 14),  # PaletteData row 11 ($1BD254)
        ),
        "086d4205e44e57b0427b7ea95b27c8b9",
        "four US file-select palettes (CGRAM rows 5/7/9/11, PaletteData"
        " slices, bank $1B)",
    ),
    UsAsset(
        "us_gfx_16.3bppc",
        (Slice(0x091D5B, 0x517),),
        "fc2697787500a0c950d51d3698d8e21f",
        "US title-screen intro-tileset sheet 1/4 (compressed slice;"
        " $129D5B LoROM; --us-title-screen only)",
    ),
    UsAsset(
        "us_gfx_17.3bppc",
        (Slice(0x092272, 0x48C),),
        "169b7dcab583eb1435203fddd3d620e9",
        "US title-screen intro-tileset sheet 2/4 (compressed slice;"
        " $12A272 LoROM; --us-title-screen only)",
    ),
    UsAsset(
        "us_gfx_1d.3bppc",
        (Slice(0x093840, 0x514),),
        "060c48c1126ec8a0b86770a80d9285fe",
        "US title-screen intro-tileset sheet 3/4 (compressed slice;"
        " $12B840 LoROM; --us-title-screen only)",
    ),
    UsAsset(
        "us_gfx_1e.3bppc",
        (Slice(0x093D54, 0x475),),
        "a77cae817bd90efdb718fdfb78850b3c",
        "US title-screen intro-tileset sheet 4/4 (compressed slice;"
        " $12BD54 LoROM; --us-title-screen only)",
    ),
    UsAsset(
        "us_gfx_40.3bppc",
        (Slice(0x09E7AF, 0x536),),
        "ac3dd8110618c97b07cdbc3b404a12d5",
        "US title-logo BG art, sheet 1/2 (compressed slice; $13E7AF LoROM;"
        " --us-title-screen only)",
    ),
    UsAsset(
        "us_gfx_41.3bppc",
        (Slice(0x09ECE5, 0x560),),
        "f7544b5fefc20df1a12f48594bb1a10c",
        "US title-logo BG art, sheet 2/2 (compressed slice; $13ECE5 LoROM;"
        " --us-title-screen only)",
    ),
    UsAsset(
        "us_gfx_7b.3bpp",
        (Slice(0x08A000, 0x600),),
        "bacde442b8613ead71040b2d81496022",
        "US title-screen triforce+sword OBJ sheet (uncompressed slice;"
        " $11A000 LoROM; --us-title-screen only)",
    ),
    UsAsset(
        "us_gfx_a5.3bppc",
        (Slice(0x0B3E6B, 0x2D2),),
        "179e92e6b88edd176a510ab2a7dce64e",
        "US sword-blade/hilt OBJ sheet, GFX_A5 (compressed slice; $16BE6B"
        " LoROM; --us-title-screen only)",
    ),
)

_BY_NAME = {asset.filename: asset for asset in US_ASSETS}


def asset(filename: str) -> UsAsset:
    """The :class:`UsAsset` for ``filename`` (raises if unknown)."""
    return _BY_NAME[filename]


def _load_template() -> Template:
    """The ``binextract-us.py`` source template -- a bundled package resource
    (``.py.template``, so its name makes clear it is not itself runnable
    Python), filled in by :func:`render_binextract_us`.
    """
    text = (
        resources.files("alttp_jp_english_patcher")
        .joinpath("resources", "binextract_us.py.template")
        .read_text(encoding="utf-8")
    )
    return Template(text)


def render_binextract_us() -> str:
    """The full source of ``binextract-us.py``, generated from
    :data:`US_ASSETS` -- the deployed extractor and :func:`asset`'s sizing can
    never disagree, since both read the same table.
    """
    asset_list = "\n".join(
        f"  * {a.filename:<16} -- {a.comment}" for a in US_ASSETS
    )
    asset_table = "\n".join(
        "    ({filename!r}, ({slices}), {md5!r}, {comment!r}),".format(
            filename=a.filename,
            slices=", ".join(
                f"({s.offset:#x}, {s.length:#x})" for s in a.slices
            )
            + ("," if len(a.slices) == 1 else ""),
            md5=a.md5,
            comment=a.comment,
        )
        for a in US_ASSETS
    )
    return _load_template().substitute(
        us_rom_md5=repr(US_ROM_MD5),
        asset_list=asset_list,
        asset_table=asset_table,
    )
