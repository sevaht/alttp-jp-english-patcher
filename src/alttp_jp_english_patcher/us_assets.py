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
)

_BY_NAME = {asset.filename: asset for asset in US_ASSETS}


def asset(filename: str) -> UsAsset:
    """The :class:`UsAsset` for ``filename`` (raises if unknown)."""
    return _BY_NAME[filename]


_TEMPLATE = '''\
#!/usr/bin/env python3
"""
binextract-us.py -- regenerate the US ROM-derived font/menu assets for the
English translation from your own US ROM. Nothing copyrighted is committed to
this repo; the `binextract.py` stub runs this (and binextract-jp.py) to
produce the `bin/gfx/us_*` files.

    python3 binextract-us.py              # uses ./alttp-us.sfc
    python3 binextract-us.py --us-rom US.sfc

You need the US ROM (md5 {us_rom_md5}), by default named `alttp-us.sfc` in
this directory. (The JP 1.0 binaries come from binextract-jp.py.)
All outputs are derived from the US ROM, written under bin/gfx/ (alongside
the base disassembly's own JP-ROM-derived files there):
{asset_list}
Every output is a plain ROM byte slice -- NO emulator is used. Each is checked
against a known md5; if any check fails the script stops loudly.

GENERATED from alttp_jp_english_patcher/us_assets.py -- do not hand-edit;
change that table and redeploy to regenerate this file.
"""
import argparse, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bin", "gfx")

US_ROM_MD5 = {us_rom_md5!r}

# (filename, ((offset, length), ...), expected md5, comment)
ASSETS = (
{asset_table}
)


def md5(b):
    return hashlib.md5(b).hexdigest()


def die(msg):
    print("ERROR:", msg, file=sys.stderr)
    sys.exit(1)


def check_rom(path):
    if not path or not os.path.isfile(path):
        die(f"US ROM not found: {{path!r}}")
    got = md5(open(path, "rb").read())
    if got != US_ROM_MD5:
        die(
            f"US ROM md5 mismatch: got {{got}}, expected {{US_ROM_MD5}}\\n"
            f"       (this must be the US release)"
        )
    print(f"  US ROM ok ({{got}})")


def extract(us_bytes, name, slices, want, comment):
    data = b"".join(
        us_bytes[offset : offset + length] for offset, length in slices
    )
    got = md5(data)
    out = os.path.join(OUT, name)
    open(out, "wb").write(data)
    ok = got == want
    status = "OK" if ok else "MD5 MISMATCH"
    print(f"  bin/gfx/{{name:<16}} {{got}}  [{{status}}]  # {{comment}}")
    return ok


def main():
    ap = argparse.ArgumentParser(
        description="extract the US ROM-derived font/menu assets for the"
        " English build"
    )
    ap.add_argument(
        "--us-rom",
        default=os.path.join(HERE, "alttp-us.sfc"),
        help="US ROM (default: ./alttp-us.sfc)",
    )
    a = ap.parse_args()

    a.us_rom = os.path.abspath(a.us_rom)
    print("Validating ROM:")
    check_rom(a.us_rom)
    os.makedirs(OUT, exist_ok=True)

    print("Extracting assets:")
    us = open(a.us_rom, "rb").read()
    ok = True
    for name, slices, want, comment in ASSETS:
        ok &= extract(us, name, slices, want, comment)

    if not ok:
        die(
            "one or more assets did not match the expected md5.\\n"
            "       Double-check that your US ROM matches the md5 at the"
            " top of this script."
        )
    print("\\nUS assets extracted and verified.")


if __name__ == "__main__":
    main()
'''


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
    return _TEMPLATE.format(
        us_rom_md5=US_ROM_MD5, asset_list=asset_list, asset_table=asset_table
    )
