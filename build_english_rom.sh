#!/usr/bin/env bash
#
# build_english_rom.sh — build an English version of the Japanese 1.0 ROM.
# ONE command. You supply two ROMs you legally own; nothing else is needed.
#
#   ./build_english_rom.sh --jp-rom YOUR_JP1.0.sfc --us-rom YOUR_US.sfc
#
# Output: alttp_english.sfc  (play it in any SNES emulator)
#
set -euo pipefail
cd "$(dirname "$0")"

usage() {
  cat <<EOF

Build an English version of the Zelda: A Link to the Past Japanese 1.0 ROM.

USAGE:
  ./build_english_rom.sh --jp-rom <file> --us-rom <file> [--out <file>]

YOU PROVIDE TWO ROMS YOU OWN:
  --jp-rom   Japanese 1.0 ROM   (md5 03a63945398191337e896e5771f77173)
  --us-rom   US ROM             (md5 608c22b8ff930c62dc2de54bcd6eba72)
  --out      output name        (default: alttp_english.sfc)

EOF
  exit 1
}

JP="" ; US="" ; OUT="alttp_english.sfc"
while [ $# -gt 0 ]; do
  case "${1:-}" in
    --jp-rom) JP="${2:-}"; shift 2 ;;
    --us-rom) US="${2:-}"; shift 2 ;;
    --out)    OUT="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done
[ -n "$JP" ] && [ -n "$US" ] || usage

# ---- check required tools, with plain-English fixes ----
MISS=0
miss() { echo "  MISSING: $1  ->  $2"; MISS=1; }
command -v python3 >/dev/null 2>&1 || miss "python3" "install Python 3"
command -v gcc     >/dev/null 2>&1 || miss "gcc"     "install gcc (e.g. 'sudo apt install build-essential')"
[ -f asarmon.exe ] || miss "asarmon.exe" "this file should already be in the repo; re-clone if it's gone"
if command -v asarmon >/dev/null 2>&1; then ASAR=(asarmon)
elif command -v wine >/dev/null 2>&1; then ASAR=(wine asarmon.exe)
else miss "wine" "install wine to run asarmon.exe (e.g. 'sudo apt install wine')"; fi
if [ "$MISS" != 0 ]; then echo; echo "Install the tool(s) above, then run this again."; exit 1; fi

# ---- check the ROMs exist (md5 is checked by the extractor) ----
[ -f "$JP" ] || { echo "JP ROM not found: $JP"; exit 1; }
[ -f "$US" ] || { echo "US ROM not found: $US"; exit 1; }

echo "==> [1/4] Placing your JP ROM as ./alttp.sfc"
if [ "$(readlink -f "$JP")" != "$(readlink -f alttp.sfc 2>/dev/null)" ]; then cp -f "$JP" alttp.sfc; fi

echo "==> [2/4] Building the English font assets from your ROMs (first run downloads a small emulator core)"
python3 extract_english_assets.py --jp-rom alttp.sfc --us-rom "$US"

echo "==> [3/4] Extracting the game's graphics/audio from your JP ROM"
python3 binextract.py

echo "==> [4/4] Assembling $OUT"
LOG="$(mktemp)"
# Run asar inside an `if` so a non-zero exit doesn't trip `set -e` (no `|| true` needed —
# that would discard asar's exit code, and a failed run can still leave a partial file that
# passes the -s check). asar exits 0 only on success; retry to ride out rare wine flakiness.
BUILD_OK=0
for attempt in 1 2 3; do
  rm -f "$OUT"
  if "${ASAR[@]}" -wnoW1006 -wnoW1030 --fix-checksum=on main.asm "$OUT" >"$LOG" 2>&1 && [ -s "$OUT" ]; then
    BUILD_OK=1; break
  fi
  echo "  (assembler attempt $attempt failed — retrying)"
done
if [ "$BUILD_OK" != 1 ]; then
  echo "  BUILD FAILED. Assembler output:"
  grep -vE 'libEGL|pci id|xrandr|winediag|nouveau|fixme:|GetCurrentPackage' "$LOG" | sed 's/^/    /'
  rm -f "$LOG"; exit 1
fi
rm -f "$LOG"

MD5=$(md5sum "$OUT" | cut -d' ' -f1)
echo
echo "SUCCESS -> $OUT  ($(stat -c%s "$OUT") bytes, md5 $MD5)"
REFERENCE_MD5="f643ecd1994e0eccb14516c71b18b3ae"
if [ "$MD5" = "$REFERENCE_MD5" ]; then
  echo "  (verified: matches the reference English build)"
else
  echo "  (note: differs from the reference build $REFERENCE_MD5 —"
  echo "   this is fine if you intended source changes; otherwise double-check your ROMs)"
fi
echo "Play it in any SNES emulator. Enjoy the English JP 1.0 ROM."
