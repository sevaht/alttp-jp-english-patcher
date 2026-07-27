#!/usr/bin/env bash
# apply.sh -- deploy the English graft into a pristine jpdasm checkout.
#
# Turns a fork of spannerisms/jpdasm into a functional English translation by:
#   1. generating the whole English program  (scripts/generate.py): the base
#      banks hooked in place, the graft banks bank_20..bank_2E beside them, and
#      main.asm wired (bank_2X includes + 2 MB padding) -- all in one Rom pass
#   2. copying the asset extractor + build tooling
#   3. updating .gitignore (ROM-derived binaries stay out of git)
# The target ends up clean -- only the translation, none of this generator.
#
# Sources are fetched into .deps/ (gitignored) if missing:
#   * snes-assembly-parser  (the parser library)
#   * usdasm                (US disassembly -- pulled FROM)
#   * jpdasm                (pristine JP -- generate.py --jpdasm base reference)
#
# Usage:
#   ./apply.sh --target /path/to/jpdasm-fork [--us-rom US.sfc] [--jp-rom JP.sfc]
#              [--baseline] [--verify]
#
#   --target    the jpdasm fork to write into (required)
#   --us-rom    if given, extract the ROM-derived binaries into the target now;
#               otherwise the target gets extract_english_assets.py to run later
#   --jp-rom    JP 1.0 ROM (asset-extraction md5 check; default: target/alttp.sfc)
#   --baseline  emit the change-free baseline (no base hooks, no graft edits)
#               -- the clean base for a review diff
#   --verify    after deploying, run the base-edit regression check
#
# Source overrides (DIR = use this checkout, skip fetching):
#   SNES_PARSER_DIR / SNES_PARSER_URL / SNES_PARSER_REF   (default ref: main)
#   USDASM_DIR      / USDASM_URL      / USDASM_REF         (default ref: main)
#   JPDASM_DIR      / JPDASM_URL      / JPDASM_REF         (default ref: master)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

target="" ; us_rom="" ; jp_rom="" ; baseline="" ; verify=""
while [ $# -gt 0 ]; do
    case "${1:-}" in
        --target)   target="${2:-}"; shift 2 ;;
        --us-rom)   us_rom="${2:-}"; shift 2 ;;
        --jp-rom)   jp_rom="${2:-}"; shift 2 ;;
        --baseline) baseline="--baseline"; shift ;;
        --verify)   verify="1"; shift ;;
        -h|--help)  grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown argument: $1" >&2; exit 1 ;;
    esac
done

command -v python3 >/dev/null 2>&1 || { echo "error: python3 not found" >&2; exit 1; }
command -v git     >/dev/null 2>&1 || { echo "error: git not found" >&2; exit 1; }
[ -n "$target" ] || { echo "error: --target <jpdasm-fork> is required" >&2; exit 1; }
target="$(cd "$target" && pwd)"
[ -f "$target/bank_00.asm" ] && [ -f "$target/main.asm" ] || {
    echo "error: $target does not look like a jpdasm checkout" >&2; exit 1; }

deps="$here/.deps"
mkdir -p "$deps"

# fetch_repo LABEL DIR URL REF SENTINEL MODE
#   MODE=update  -> refresh a git checkout to REF (managed dep)
#   MODE=once    -> clone only if missing; leave an existing checkout untouched
fetch_repo() {
    local label="$1" dir="$2" url="$3" ref="$4" sentinel="$5" mode="$6"
    if [ -e "$dir/$sentinel" ]; then
        if [ "$mode" = update ] && [ -d "$dir/.git" ]; then
            echo "$label: updating ($ref)"
            git -C "$dir" fetch --quiet --depth 1 origin "$ref"
            git -C "$dir" reset --hard --quiet FETCH_HEAD
        else
            echo "$label: using existing $dir"
        fi
    else
        echo "$label: cloning ($ref)"
        git clone --quiet --depth 1 --branch "$ref" "$url" "$dir"
    fi
    [ -e "$dir/$sentinel" ] || { echo "error: $dir/$sentinel missing" >&2; exit 1; }
}

parser="${SNES_PARSER_DIR:-$deps/snes-assembly-parser}"
usdasm="${USDASM_DIR:-$deps/usdasm}"
jpdasm="${JPDASM_DIR:-$deps/jpdasm}"
fetch_repo "snes-assembly-parser" "$parser" \
    "${SNES_PARSER_URL:-https://github.com/nacitar/snes-assembly-parser.git}" \
    "${SNES_PARSER_REF:-main}" "src/snes_assembly_parser" \
    "$([ -n "${SNES_PARSER_DIR:-}" ] && echo once || echo update)"
fetch_repo "usdasm" "$usdasm" \
    "${USDASM_URL:-https://github.com/spannerisms/usdasm.git}" \
    "${USDASM_REF:-main}" "bank_0E.asm" once
fetch_repo "jpdasm" "$jpdasm" \
    "${JPDASM_URL:-https://github.com/spannerisms/jpdasm.git}" \
    "${JPDASM_REF:-master}" "bank_00.asm" once

export PYTHONPATH="$parser/src:$here/scripts"
run_py() { python3 "$here/scripts/$@"; }

echo "==> generating the English program -> $target"
# generate.py loads the pristine JP as one Rom, folds in every relocated
# subsystem, hooks the base banks to reach them, wires main.asm (graft-bank
# includes + 2 MB padding), and writes the entire fork -- base banks hooked in
# place, graft banks bank_20 .. bank_2E beside them.
run_py generate.py --usdasm "$usdasm" --jpdasm "$jpdasm" \
    --out "$target" $baseline

echo "==> copying build tooling"
cp "$here/extract_english_assets.py" "$here/build_english_rom.sh" "$target/"
chmod +x "$target/build_english_rom.sh"

echo "==> updating .gitignore (ROM-derived binaries)"
python3 "$here/scripts/gitignore.py" "$target/.gitignore"

if [ -n "$us_rom" ]; then
    echo "==> extracting ROM-derived binaries from $us_rom"
    ( cd "$target" && python3 extract_english_assets.py \
        ${jp_rom:+--jp-rom "$jp_rom"} --us-rom "$us_rom" )
else
    echo "note: no --us-rom given; run this in $target before building:"
    echo "        python3 extract_english_assets.py --jp-rom JP.sfc --us-rom US.sfc"
fi

if [ -n "$verify" ]; then
    echo "==> verifying base edits"
    run_py verify_base.py --src "$jpdasm" --usdasm "$usdasm"
fi

echo "done. build the target with:  cd $target && ./build_english_rom.sh --jp-rom JP.sfc --us-rom US.sfc"
