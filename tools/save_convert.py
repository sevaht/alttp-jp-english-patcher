#!/usr/bin/env python3
"""Convert an A Link to the Past battery save (.srm) between the US format and the
Japanese-1.0 format used by THIS repo's English build, and/or set a file's name from ASCII.

    # convert a US save to our JP-1.0 English build's format (6-char name, relocated)
    tools/save_convert.py --to jp  US.srm  out.srm

    # convert our JP save to the US format
    tools/save_convert.py --to us  JP.srm  out.srm

    # set file 1's name (ASCII); format auto-detected, or force with --to
    tools/save_convert.py --set-name 1 "LINK"  in.srm  out.srm

    # both at once
    tools/save_convert.py --to jp --set-name 1 "Zelda"  US.srm  out.srm

    # NORMAL (kana) Japanese save: its name can't be mapped, so keep the name already in the
    # destination. Pre-prepare your name in the target ROM (creating out.srm), then:
    tools/save_convert.py --to jp --keep-names  VANILLA_JP.srm  out.srm
    # (a destination slot with no save falls back to "LINK" for JP / "Link" for US)

WHY THIS WORKS
  The two builds share the SAME save layout for everything except the player-name field:
  both store a 6-character name (12 bytes), but the US field sits at $3D9 while our English
  build widened it backward to $3D5 (into previously-unused bytes) so it fits before the JP
  checksum marker; every field after the name is shifted by 4 bytes. The item/progress data
  before the name is identical. Because this repo's file-select/name-entry was grafted FROM
  the US ROM, the per-character name ENCODING is identical, so full 6-char names transfer.

  Each $500-byte save slot ends with a checksum word so the whole slot sums to $5A5A; this
  script recomputes it. The .srm holds 3 slots at $000/$500/$A00 plus backup mirrors at
  main+$F00; every $500-aligned region that validates as a save is converted.
"""
import argparse, sys

SLOT_SIZE      = 0x500
PRENAME_BYTES  = 0x3D4          # item/progress data $000-$3D3, identical both formats
JP_NAME_OFF    = 0x3D5          # our English build: 6-word name field (widened forward
US_NAME_OFF    = 0x3D9          #   into $3D5-$3D8) ending just before SCHKSM at $3E1
NAME_CHARS     = 6             # both formats now store a 6-character name
JP_MARKER_OFF  = 0x3E1          # SCHKSM ($55AA) sits right after each name field
US_MARKER_OFF  = 0x3E5
MARKER         = 0x55AA
POSTNAME_BYTES = 34             # SCHKSM + 14 dungeon counters + GPNOW + GAMESPLAYED = 17 words
ICKSM_OFF      = 0x4FE          # SAVEICKSM: the adjustment word (last word of the slot)
CKSUM_TARGET   = 0x5A5A         # a valid slot's 0x280 words sum to this
MIRROR_DELTA   = 0xF00          # backup copy of slot N lives at (slot N base) + $F00
OUR_TAG_OFF    = 0x410          # word tagging our format for the in-ROM save migrator
OUR_TAG        = 0x0006         # (unused by vanilla US/JP -- their erase zeroes the slot)
DEFAULT_NAME_JP = "LINK"        # fallback name when --keep-names finds nothing to borrow
DEFAULT_NAME_US = "Link"

def name_off(fmt):   return US_NAME_OFF if fmt == 'us' else JP_NAME_OFF
def marker_off(fmt): return US_MARKER_OFF if fmt == 'us' else JP_MARKER_OFF

# --- name code table (stored per-character CODE <-> ASCII) -----------------------------------
# Uppercase A-Z = $00-$19 but 'I' is the narrow tile $5F; lowercase a-z = $1A-$33 but 'i' is
# $60; '!' = $61; digits 0-9 = $76-$7F; space = $59. (Derived from NameFile_CharacterLayout +
# RenderText_FilterName's I/i/! special cases + the encode_lower digit branch.)
def _build_ascii_to_code():
    m = {}
    for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"): m[c] = 0x00 + i
    m['I'] = 0x5F
    for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"): m[c] = 0x1A + i
    m['i'] = 0x60
    for i, c in enumerate("0123456789"): m[c] = 0x76 + i
    m['!'] = 0x61
    m[' '] = 0x59
    return m
ASCII_TO_CODE = _build_ascii_to_code()

def encode_name_word(code):  # per-character CODE -> stored 16-bit word (nibble-spread)
    return ((code & 0xFFF0) << 1) | (code & 0x000F)

def name_word_for_char(ch):
    if ch not in ASCII_TO_CODE:
        raise ValueError(f"character {ch!r} is not supported in a name "
                         f"(allowed: A-Z a-z 0-9 space and '!')")
    return encode_name_word(ASCII_TO_CODE[ch])

# --- low-level helpers -----------------------------------------------------------------------
def rd16(b, o): return b[o] | (b[o + 1] << 8)
def wr16(b, o, v): b[o] = v & 0xFF; b[o + 1] = (v >> 8) & 0xFF

def slot_sum(slot):
    return sum(rd16(slot, 2 * i) for i in range(0x280)) & 0xFFFF

def slot_valid(slot):
    return slot_sum(slot) == CKSUM_TARGET

def fix_checksum(slot):
    wr16(slot, ICKSM_OFF, 0x0000)
    wr16(slot, ICKSM_OFF, (CKSUM_TARGET - slot_sum(slot)) & 0xFFFF)

def detect_format(slot):
    if rd16(slot, JP_MARKER_OFF) == MARKER: return 'jp'
    if rd16(slot, US_MARKER_OFF) == MARKER: return 'us'
    return None

# --- slot transforms -------------------------------------------------------------------------
def convert_slot(slot, target):
    """Return a new 0x500 slot converted to `target` ('jp'/'us'). No-op if already there."""
    src = detect_format(slot)
    if src is None or src == target:
        return bytearray(slot)
    new = bytearray(SLOT_SIZE)
    new[0:PRENAME_BYTES] = slot[0:PRENAME_BYTES]               # identical item/progress data
    so, do = name_off(src), name_off(target)
    for i in range(NAME_CHARS):                               # relocate the 6-word name field
        wr16(new, do + 2 * i, rd16(slot, so + 2 * i))
    sm, dm = marker_off(src), marker_off(target)
    new[dm:dm + POSTNAME_BYTES] = slot[sm:sm + POSTNAME_BYTES]  # SCHKSM + counters + games
    if target == 'jp':                                         # tag ours so the in-ROM
        wr16(new, OUR_TAG_OFF, OUR_TAG)                        # migrator leaves it alone
    fix_checksum(new)                                          # unused tail/gaps stay zero
    return new

def set_slot_name(slot, text):
    """Write `text` (ASCII) into the slot's name field, in the slot's current format."""
    fmt = detect_format(slot)
    if fmt is None:
        raise ValueError("slot is not a valid save (can't tell US vs JP), refusing to set name")
    if len(text) > NAME_CHARS:
        print(f"  note: name {text!r} is longer than {NAME_CHARS} chars; "
              f"truncating to {text[:NAME_CHARS]!r}", file=sys.stderr)
    chars = list(text[:NAME_CHARS]) + [' '] * (NAME_CHARS - len(text))  # pad with spaces
    off = name_off(fmt)
    for i, ch in enumerate(chars):
        wr16(slot, off + 2 * i, name_word_for_char(ch))
    fix_checksum(slot)
    return slot

def copy_slot_name(dst_slot, src_slot):
    """Copy the raw 6-word name field from src_slot into dst_slot (each at its own format's
    offset). Lossless — carries the exact stored words, so it works even for a vanilla-Japanese
    (kana) name; only sensible if src is already in the target's char set."""
    so = name_off(detect_format(src_slot))
    do = name_off(detect_format(dst_slot))
    for i in range(NAME_CHARS):
        wr16(dst_slot, do + 2 * i, rd16(src_slot, so + 2 * i))
    fix_checksum(dst_slot)
    return dst_slot

# --- whole-file driver -----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="input .srm")
    ap.add_argument("output", help="output .srm")
    ap.add_argument("--to", choices=("jp", "us"), help="convert every save to this format")
    ap.add_argument("--set-name", nargs=2, action="append", default=[],
                    metavar=("SLOT", "NAME"), help="set file SLOT (1-3) name to ASCII NAME "
                    "(repeatable; applied last, overrides --keep-names)")
    ap.add_argument("--keep-names", action="store_true",
                    help="ignore the SOURCE name and instead keep the name already in each "
                    "destination slot (read from OUTPUT before overwriting, so pre-prepare it "
                    "in the target ROM). Empty destination slots default to LINK (JP) / Link "
                    "(US). Use this for a normal Japanese save whose kana name can't be mapped.")
    a = ap.parse_args()
    if not a.to and not a.set_name and not a.keep_names:
        ap.error("nothing to do: pass --to, --keep-names, and/or --set-name")

    data = bytearray(open(a.input, "rb").read())

    # for --keep-names: read the EXISTING output (pre-prepared names) before we overwrite it
    dest_data = None
    if a.keep_names:
        try:
            dest_data = open(a.output, "rb").read()
        except OSError:
            dest_data = None  # no pre-prepared file -> every slot falls back to the default

    # every $500-aligned region that validates as a save (3 slots + their +$F00 mirrors)
    regions = [off for off in range(0, len(data) - SLOT_SIZE + 1, SLOT_SIZE)
               if slot_valid(data[off:off + SLOT_SIZE])]
    if not regions:
        sys.exit("no valid save slots found in the input .srm (wrong file / corrupt?)")

    if a.to:
        for off in regions:
            slot = data[off:off + SLOT_SIZE]
            src = detect_format(slot)
            data[off:off + SLOT_SIZE] = convert_slot(slot, a.to)
            if src and src != a.to:
                print(f"  slot @0x{off:04X}: {src.upper()} -> {a.to.upper()}")

    if a.keep_names:
        for n in range(1, 4):                                  # per logical file 1-3
            base = (n - 1) * SLOT_SIZE
            if base + SLOT_SIZE > len(data) or not slot_valid(data[base:base + SLOT_SIZE]):
                continue
            tgt_fmt = detect_format(data[base:base + SLOT_SIZE])
            # borrow from the same slot in the pre-prepared output, if it holds a save
            src_name = None
            if dest_data and base + SLOT_SIZE <= len(dest_data):
                cand = bytearray(dest_data[base:base + SLOT_SIZE])
                if detect_format(cand) is not None:
                    src_name = cand
            for off in (base, base + MIRROR_DELTA):            # keep main + mirror consistent
                if off + SLOT_SIZE > len(data) or not slot_valid(data[off:off + SLOT_SIZE]):
                    continue
                slot = data[off:off + SLOT_SIZE]
                if src_name is not None:
                    data[off:off + SLOT_SIZE] = copy_slot_name(slot, src_name)
                else:
                    default = DEFAULT_NAME_US if tgt_fmt == 'us' else DEFAULT_NAME_JP
                    data[off:off + SLOT_SIZE] = set_slot_name(slot, default)
            print(f"  file {n}: name kept from destination"
                  if src_name is not None else f"  file {n}: no destination name, defaulted to "
                  f"{(DEFAULT_NAME_US if tgt_fmt=='us' else DEFAULT_NAME_JP)!r}")

    for slot_s, name in a.set_name:
        n = int(slot_s)
        if not 1 <= n <= 3:
            sys.exit(f"--set-name slot must be 1-3, got {slot_s}")
        base = (n - 1) * SLOT_SIZE
        touched = False
        for off in (base, base + MIRROR_DELTA):               # main + backup mirror
            if off + SLOT_SIZE <= len(data) and slot_valid(data[off:off + SLOT_SIZE]):
                data[off:off + SLOT_SIZE] = set_slot_name(data[off:off + SLOT_SIZE], name)
                touched = True
        if not touched:
            sys.exit(f"file {n} has no valid save to rename")
        print(f"  file {n}: name set to {name!r}")

    open(a.output, "wb").write(data)
    print(f"wrote {a.output} ({len(data)} bytes)")

if __name__ == "__main__":
    main()
