# tools/ — headless test & inspection toolkit

This is the self-verification kit built for the English translation. It lets an
agent (or you) drive the ROM in a headless emulator, screenshot any screen, and
dump WRAM / VRAM / SRAM for inspection — no GUI, no manual play required.

These are standalone dev/test scripts, not part of the `alttp_jp_english_patcher`
package (no import dependency either way) — build a ROM with the patcher first
(see the top-level README), then point these at it. Excluded from the package's
lint/type-check config the same way `deploy/` is, since they predate and don't
share its style.

## runner.c — headless libretro frontend

A ~170-line C frontend that `dlopen`s a libretro core, runs the ROM for N frames
with scripted controller input, and writes PPM screenshots plus memory dumps.

### Build
```
# grab a prebuilt snes9x core + header (once):
curl -sL https://buildbot.libretro.com/nightly/linux/x86_64/latest/snes9x_libretro.so.zip -o core.zip && unzip -o core.zip
curl -sLO https://raw.githubusercontent.com/libretro/libretro-common/master/include/libretro.h
gcc -O2 -o runner runner.c -ldl
```

### Run
```
runner <core.so> <rom.sfc> <out_prefix> <total_frames> [every] [a-b:BUTTON ...]
```
- `every` (optional): dump a screenshot every N frames.
- `a-b:BUTTON`: hold BUTTON on frames a..b. BUTTON ∈ START SELECT A B X Y L R UP DOWN LEFT RIGHT.
- `SRM=path runner ...`: load a `.srm` save (via env var).

Outputs: `prefix_NNNN.ppm` + `prefix_final.ppm` (256x224, RGB565→PPM), and
`prefix_wram.bin` (128 KB, `$7E0000-$7FFFFF`), `prefix_sram.bin`, and
`prefix_vram.bin` (64 KB VRAM, via `RETRO_MEMORY_VIDEO_RAM` = id 3 — snes9x
libretro exposes VRAM there; this was the key to solving the menu-font work).

Convert a PPM to PNG with ImageMagick: `magick x.ppm x.png` (or `convert`).

### Example: open the item menu and screenshot it
```
# boot, mash START/A through the intro to ~frame 6000 (in-house control),
# then START to open the menu:
SRM=lttp_jp10_english.srm runner ./snes9x_libretro.so rom.sfc menu 6400 0 \
  1000-1015:START 1120-1135:START 1240-1255:START \
  1400-1404:A 1520-1524:A 1640-1644:A ... 6050-6065:START
```

## mesen_runner.py — accurate (Mesen) headless frontend

`runner.c`'s snes9x core is fast but **lenient about vblank timing and rendering** —
vblank overruns and subtle PPU/compositing bugs can look fine there yet break on real
hardware. `mesen_runner.py` drives **Mesen** instead (accurate, hardware-like) under
Xvfb, and is what all the file-select/name-screen visual work was verified against.

```
python3 tools/mesen_runner.py <rom> <out_prefix> <total_frames> [every] [a-b:BUTTON ...]
```
- Same `every` / `a-b:BUTTON` / `SRM=path` interface as `runner`.
- Outputs `<prefix>_<frame>.png` (+ `_final.png`), converting PPM→PNG via ImageMagick.
- Locates Mesen via `$MESEN`, then `tools/mesen/Mesen`, else **downloads MesenCE**
  (Linux x64) into `tools/mesen/` and patches its `settings.json` to allow Lua
  `io`/`os` access and a long script timeout. Mesen is portable — its data
  (`settings.json`, `Saves/`) lives beside the binary; `.srm` saves go in
  `tools/mesen/Saves/<rom>.srm`.
- Input is injected by writing ALttP's joypad WRAM each frame (`$7E00F0/F4` = A-group
  `BYsSudlr`, `$7E00F2/F6` = B-group `AXLR`), because Mesen's `setInput` doesn't
  register in this headless build.

Use `runner` for fast scripted dumps and asset extraction; use `mesen_runner.py` to
verify anything visual (backgrounds, palettes, box layout, fonts).

## save_convert.py — .srm US <-> JP converter + name editor

Converts a battery save between the **US** format and the **JP-1.0 format used by this
repo's English build**, and/or sets a file's name from ASCII.

```
tools/save_convert.py --to jp  US.srm  out.srm      # US save -> our build (names -> 4 chars)
tools/save_convert.py --to us  JP.srm  out.srm      # our save -> US       (names -> 6 chars)
tools/save_convert.py --set-name 1 "LINK"  in.srm out.srm     # rename file 1 (format auto-detected)
tools/save_convert.py --to jp --set-name 1 "Zelda"  US.srm out.srm    # both

# NORMAL (kana) Japanese save — its name can't be mapped, so keep the destination's name.
# Pre-prepare your name in the target ROM (making out.srm), then:
tools/save_convert.py --to jp --keep-names  VANILLA_JP.srm  out.srm
```

The only format difference between US and this build's JP is the player-name field (US = 6
chars, JP = 4) and a 4-byte shift of every field after it; the item/progress data before the
name is identical, and — because this build's name-entry was grafted from the US ROM — the
per-character name encoding is the same, so names transfer as-is (truncated/padded). Each
`$500` save slot's checksum is recomputed (the slot's `0x280` words must sum to `$5A5A`); all
3 slots and their `+$F00` backup mirrors are handled. `--set-name` accepts `A-Z a-z 0-9`,
space, and `!`.

A **normal (unmodified) Japanese** save has the same layout but kana names that can't be shown
in English. Use `--keep-names`: it ignores the source name and instead keeps the name already
in each *destination* slot — so pre-prepare your name by playing the target ROM and naming a
file (creating the output `.srm`), then convert into it. A destination slot with no save falls
back to `LINK` (JP target) / `Link` (US target). `--set-name` still overrides per slot.

Validated end-to-end against both real ROMs: a JP save `--to us` loads in `us.sfc` with correct
names; `--set-name`/truncation round-trips into this build's ROM; and `--keep-names` borrows the
pre-prepared destination name (or the LINK/Link default, confirmed on the file-select).

## link_intro.srm — test save

`SRM=tools/link_intro.srm ./runner ...` loads file 1 = "LINK" positioned at the intro,
for reproducing dialogue and the uncle's `[NAME]` message. It has **no items**, so the
inventory item-name text won't display — use a save with items to verify those.

## render_tiles.py — 2bpp tile viewer

Renders SNES 2bpp tiles from any binary dump (VRAM/WRAM/ROM) to a PNG so you can
*see* a font's tile layout. The file-select font is 2-tiles-tall (top tile + tile
`+0x10`); use `--stacked` to view whole glyphs. See the file header for examples.

**Lesson baked into this tool:** never deduce a font's tile mapping — render it.
Deducing the file-select layout put 'H' at the wrong tile and produced a garbled
character; rendering the font from a VRAM dump gave the correct map immediately.
