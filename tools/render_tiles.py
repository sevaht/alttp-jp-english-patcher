#!/usr/bin/env python3
"""
render_tiles.py - render SNES 2bpp tile graphics from a binary dump to a PNG.

Used throughout the English-translation work to *see* fonts that live in VRAM or
in the WRAM decompression buffers (dumped by tools/runner.c), instead of guessing
tile layouts. Guessing a font layout is exactly what caused a broken 'H' bug in
the file-select copy/erase text - always render, don't deduce.

Examples:
  # render the in-game menu font (VRAM $E000-$FFFF, 512 tiles) from a vram dump
  python3 render_tiles.py dump_vram.bin --base 0xE000 --count 512 --out font.png

  # render a 2-tile-tall glyph font by stacking tile T with tile T+0x10
  python3 render_tiles.py dump_vram.bin --base 0xE000 --lo 0x140 --hi 0x186 \
          --stacked --out alphabet.png

SNES 2bpp tile = 16 bytes: for each of 8 rows, two bytes give bitplanes 0 and 1;
pixel value (0-3) = plane0.bit | (plane1.bit << 1). Colour 0 is transparent/bg.
"""
import argparse, struct, zlib

def tile_pixels(data, off):
    rows = []
    for y in range(8):
        p0 = data[off + y*2]; p1 = data[off + y*2 + 1]
        rows.append([((p0 >> (7-x)) & 1) | (((p1 >> (7-x)) & 1) << 1) for x in range(8)])
    return rows

def write_png(path, w, h, rgb):
    raw = bytearray()
    for y in range(h):
        raw.append(0); raw += rgb[y*w*3:(y+1)*w*3]
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0, help="byte offset of tile 0")
    ap.add_argument("--lo", type=lambda s: int(s, 0), default=0, help="first tile index")
    ap.add_argument("--hi", type=lambda s: int(s, 0), default=None, help="one past last tile index")
    ap.add_argument("--count", type=int, default=256)
    ap.add_argument("--perrow", type=int, default=16)
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--stacked", action="store_true",
                    help="each cell = tile T (top) + tile T+0x10 (bottom); for 2-tile-tall fonts")
    ap.add_argument("--out", default="tiles.png")
    a = ap.parse_args()
    data = open(a.dump, "rb").read()
    lo = a.lo
    hi = a.hi if a.hi is not None else lo + a.count
    pal = [(20, 20, 50), (120, 120, 120), (200, 200, 200), (255, 255, 255)]
    tiles = list(range(lo, hi))
    cellh = 17 if a.stacked else 8
    rows = (len(tiles) + a.perrow - 1) // a.perrow
    W, H = a.perrow * 8, rows * cellh
    img = [[0]*W for _ in range(H)]
    for i, t in enumerate(tiles):
        cx = (i % a.perrow) * 8; cy = (i // a.perrow) * cellh
        top = tile_pixels(data, a.base + t*16)
        for y in range(8):
            for x in range(8):
                img[cy+y][cx+x] = top[y][x]
        if a.stacked:
            bot = tile_pixels(data, a.base + (t + 0x10)*16)
            for y in range(8):
                for x in range(8):
                    img[cy+8+y][cx+x] = bot[y][x]
    out = bytearray(W*a.scale * H*a.scale * 3)
    for y in range(H*a.scale):
        for x in range(W*a.scale):
            r, g, b = pal[img[y//a.scale][x//a.scale]]
            d = (y*W*a.scale + x)*3; out[d:d+3] = bytes((r, g, b))
    write_png(a.out, W*a.scale, H*a.scale, bytes(out))
    print(f"wrote {a.out}  ({len(tiles)} tiles, {a.perrow}/row, base {a.base:#x})")

if __name__ == "__main__":
    main()
