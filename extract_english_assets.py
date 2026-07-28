#!/usr/bin/env python3
"""
extract_english_assets.py — regenerate the ROM-derived font assets for the English
translation from your own ROMs. Nothing copyrighted is committed to this repo; run
this once (per checkout) to produce the three `english/*.bin` / `*.2bpp` files.

    python3 extract_english_assets.py --jp-rom JP1.0.sfc --us-rom US.sfc

You need BOTH ROMs:
  * JP 1.0  (md5 03a63945398191337e896e5771f77173)
  * US      (md5 608c22b8ff930c62dc2de54bcd6eba72)
All outputs are derived from the US ROM:
  * font.2bpp                  (plain ROM-offset byte slice)
  * gfx_dc.2bppc, gfx_dd.2bppc (US menu/file-select font sheets, compressed byte slices)
  * gfx_39.3bppc               (US file-select "linoleum" background sheet, compressed byte slice)
  * usfs_pal.bin               (four US file-select palettes — plain PaletteData byte slices, see
                                below and english/usfs_gfx.asm)

Every output is a plain ROM byte slice or a ROM-derived reconstruction — NO emulator is used. The
file-select palette (usfs_pal.bin) was the last hold-out: the CGRAM is composed at runtime by the
game's shared palette-load routines, but of its 256 colors only four 7-color palettes (CGRAM rows
5, 7, 9, 11) come out different from the US original on the JP ROM, and each of those is a straight
slice of the US ROM's PaletteData table. english/usfs_gfx.asm overlays just those four palettes.
Every output is checked against a known md5 — if any check fails the script stops loudly.
"""
import argparse, hashlib, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENG  = os.path.join(HERE, "english")

ROM_MD5 = {
    "jp": "03a63945398191337e896e5771f77173",
    "us": "608c22b8ff930c62dc2de54bcd6eba72",
}
# (asset, expected md5, size)
ASSET_MD5 = {
    "font.2bpp":      "56d8e02353800ed7c095791a58556274",  # US VWF font (raw slice us.sfc[0x70000:])
    "gfx_dc.2bppc":   "1dc3ce334108dc118e481a84d8368b65",  # US menu/FS font sheet (compressed slice)
    "gfx_dd.2bppc":   "e97ca7c5551d6de2ca7ca98effd99c81",  # US menu/FS font sheet (compressed slice)
    "gfx_39.3bppc":   "c79da8a80348417038634560a9486110",  # US file-select "linoleum" bg (compressed slice)
    "usfs_pal.bin":    "086d4205e44e57b0427b7ea95b27c8b9",  # four US file-select palettes (PaletteData slices)
}

def md5(b): return hashlib.md5(b).hexdigest()
def die(msg): print("ERROR:", msg, file=sys.stderr); sys.exit(1)

def check_rom(path, which):
    if not path or not os.path.isfile(path):
        die(f"{which.upper()} ROM not found: {path!r}")
    got = md5(open(path, "rb").read())
    if got != ROM_MD5[which]:
        die(f"{which.upper()} ROM md5 mismatch: got {got}, expected {ROM_MD5[which]}\n"
            f"       (this must be the {'JP 1.0' if which=='jp' else 'US'} release)")
    print(f"  {which.upper()} ROM ok ({got})")

def write_asset(name, data):
    want = ASSET_MD5[name]
    got = md5(data)
    out = os.path.join(ENG, name)
    open(out, "wb").write(data)
    ok = "OK" if got == want else "MD5 MISMATCH"
    print(f"  english/{name:<15} {got}  [{ok}]")
    return got == want

def main():
    ap = argparse.ArgumentParser(description="extract ROM-derived font assets for the English build")
    ap.add_argument("--jp-rom", default=os.path.join(HERE, "alttp.sfc"),
                    help="JP 1.0 ROM (default: ./alttp.sfc)")
    ap.add_argument("--us-rom", required=True, help="US ROM")
    a = ap.parse_args()

    a.jp_rom = os.path.abspath(a.jp_rom); a.us_rom = os.path.abspath(a.us_rom)
    print("Validating ROMs:")
    check_rom(a.jp_rom, "jp"); check_rom(a.us_rom, "us")
    os.makedirs(ENG, exist_ok=True)

    print("Extracting assets:")
    us = open(a.us_rom, "rb").read()
    ok = True

    # 1. font.2bpp — plain US ROM offset 0x70000, 0x1000 bytes
    ok &= write_asset("font.2bpp", us[0x70000:0x71000])

    # 2. Menu/file-select font sheets — plain byte slices of the US ROM's COMPRESSED graphics
    #    (no emulator). GFX_DC/GFX_DD are the only menu/file-select font sheets that differ from
    #    JP; the game's own decompressor expands them at runtime (see english/usgfx.asm and
    #    AGENTS.md §10). Offsets/sizes are from usdasm/graphics.asm:
    #      GFX_DC : $18AF0D (LoROM) -> file 0x0C2F0D, size 0x613
    #      GFX_DD : $18B520 (LoROM) -> file 0x0C3520, size 0x433
    ok &= write_asset("gfx_dc.2bppc", us[0x0C2F0D:0x0C2F0D + 0x613])
    ok &= write_asset("gfx_dd.2bppc", us[0x0C3520:0x0C3520 + 0x433])

    # 3. File-select "linoleum" background — background sheet GFX_39, the only file-select
    #    *graphic* that differs JP<->US (it is a re-colored floor tile). Compressed byte slice;
    #    repointed in english/usgfx.asm so the tileset loader decompresses it natively.
    #      GFX_39 : $13C817 (LoROM) -> file 0x09C817, size 0x351
    ok &= write_asset("gfx_39.3bppc", us[0x09C817:0x09C817 + 0x351])

    # 4. The file-select FONT is no longer an extracted asset: font.2bpp (the letters) is uploaded
    #    natively (TransferFontToVRAM = TheFont, matching the US), and the file-select glyphs/hearts
    #    are decompressed natively by LoadDefaultGraphics (LoadFileSelectGraphics restored to the US
    #    form). See AGENTS.md §10 / DETAILS.md §2.6. The former usfsfont.bin blob is gone.

    # 5. File-select palette — the four US palettes that come out different from the US original
    #    when the game's shared palette-load routines run on the JP ROM (CGRAM rows 5, 7, 9, 11,
    #    colors 1-7 each). Each is a plain slice of the US ROM's PaletteData table; usfs_gfx.asm
    #    overlays them onto the $7EC500 CGRAM buffer. Rows 5/7 are US-specific palette DATA (row 7
    #    is the wood name-banner); rows 9/11 hold identical ROM bytes JP<->US but the ported US
    #    file-select indexes a different palette there. (Offsets are PaletteData entries in bank
    #    $1B: $1BD9AA, PaletteData_owanim_00 $1BE604, PaletteData $1BD218, $1BD254.)
    #    (Row 5 looks static-unneeded -- set $06 is identical US<->JP and $1BD9AA is in set $03 --
    #    but removing it was tested and mis-coloured the wooden borders, so it is load-bearing.)
    ok &= write_asset("usfs_pal.bin",
                      us[0xDD9AA:0xDD9AA + 14] + us[0xDE604:0xDE604 + 14] +
                      us[0xDD218:0xDD218 + 14] + us[0xDD254:0xDD254 + 14])

    if not ok:
        die("one or more assets did not match the expected md5.\n"
            "       Double-check that your US ROM matches the md5 at the top of this script.")
    print("\nAll assets extracted and verified. You can now build:")
    print("  python3 binextract.py && rm -f out.sfc && wine asarmon.exe "
          "-wnoW1006 -wnoW1030 --fix-checksum=off main.asm out.sfc")

if __name__ == "__main__":
    main()
