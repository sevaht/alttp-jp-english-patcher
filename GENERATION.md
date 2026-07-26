# Generating the English translation

This repo is the **generator**. It transforms a pristine fork of
[spannerisms/jpdasm](https://github.com/spannerisms/jpdasm) into a functional
English build, keeping that fork clean of the generator itself. This document
explains what is produced, how to run it, and how to produce an isolated review
diff of the base-assembly changes.

## The two repositories

* **This repo (patcher)** — all the generative work: the Python toolkit, the
  asset extractor, and `apply.sh`.
* **The target (jpdasm fork)** — a clean fork of upstream `jpdasm`. After
  `apply.sh` it is a functional English translation: the base banks hooked in
  place, the graft's expanded-ROM banks `bank_20.asm` .. `bank_2E.asm` sitting
  beside them, a patched `main.asm`, and the build tooling. None of this
  generator is copied into it.

The target never needs a separate pristine reference: `apply.sh` fetches one
into `.deps/jpdasm` and uses it as the hook source, so the target's banks are
always derived from a known-pristine base.

## What is produced

The graft is emitted as `bank_XX.asm` files -- one per expanded-ROM bank,
following the disassembly's own convention -- so the fork reads `bank_00` ..
`bank_1F` (base) then `bank_20` .. `bank_2E` (graft):

| Output in the target | Produced by | From |
| --- | --- | --- |
| `bank_00/0C/0D/0E/13/18/1C.asm` hooks | `scripts/base_edits.py` | `.deps/jpdasm` (pristine) |
| `bank_20.asm` (VWF font + `TransferFontToVRAM`) | `scripts/generate.py` | `.deps/jpdasm` + `usdasm` |
| `bank_22.asm` / `bank_23.asm` (message data) | `scripts/generate.py` | `.deps/usdasm` |
| `bank_2C.asm` (file-select) | `scripts/generate.py` | `.deps/usdasm` + `jpdasm` |
| `bank_2D.asm` (item menu) | `scripts/generate.py` | `.deps/usdasm` + `jpdasm` |
| `bank_2E.asm` (text engine + credits) | `scripts/generate.py` | `.deps/usdasm` + `jpdasm` |
| `bank_26.asm` (US graphics sheets) | `scripts/generate.py` | `.deps/usdasm` (via incbin) |
| `bank_27.asm` (file-select palette) | `scripts/generate.py` | `.deps/usdasm` (via incbin) |
| `main.asm` includes + 2 MB padding | `scripts/mainasm.py` | — |
| `.gitignore` binary excludes | `scripts/gitignore.py` | — |
| `extract_english_assets.py`, `build_english_rom.sh` | copied | — |

`generate.py` builds every subsystem (each a self-contained function),
collects their placed (org-addressed) pieces, and groups them by ROM bank -- no
subsystem owns a file, the bank does.

The ROM-derived binaries (`english/font.2bpp`, `*.2bppc`, `*.3bppc`,
`usfs_pal.bin`) are **not** stored anywhere — they are copyrighted game data.
They are regenerated on the target from your US ROM by
`extract_english_assets.py` (run automatically when you pass `--us-rom`, or by
hand later).

* **`base_edits.py`** rewrites the pristine JP banks with the small hooks that
  make unmodified JP callers reach the relocated code: `UNREACHABLE_` renames,
  same-bank landing-pad trampolines, one inline-block `JML` redirect (the V-IRQ
  handler), and a few byte-neutral operand swaps. Every edit is declared there
  and located by label/`#_` anchor — never a line number — so it fails loud if
  upstream drifts.
* **`generate.py`** relocates every subsystem into the expanded ROM (2nd MB)
  under the `EN_` namespace, pulling what it needs *by name* from the US and/or
  JP disassembly and applying the documented English edits (no hand-maintained
  relocated assembly), then regroups the placed pieces into the per-bank
  `bank_2X.asm` files.

## Prerequisites

* `python3` and `git`. Nothing to install — the parser library is used as a bare
  checkout on `PYTHONPATH`.
* Two ROMs you own (only needed to build / extract assets, not to deploy):
  * JP 1.0 — md5 `03a63945398191337e896e5771f77173`
  * US — md5 `608c22b8ff930c62dc2de54bcd6eba72`

`apply.sh` fetches into `.deps/` (gitignored) if missing:
`snes-assembly-parser`, `usdasm` (spannerisms, `main`), `jpdasm` (spannerisms,
`master`). Override any with `SNES_PARSER_DIR` / `USDASM_DIR` / `JPDASM_DIR`
(point at an existing checkout) or the matching `_URL` / `_REF`.

## Running it

```bash
# Deploy everything and extract the ROM binaries in one go:
./apply.sh --target /path/to/jpdasm-fork --us-rom US.sfc --jp-rom JP1.0.sfc

# Deploy only (extract assets on the target later):
./apply.sh --target /path/to/jpdasm-fork

# Baseline: deploy the change-free form (no base hooks, baseline graft banks):
./apply.sh --target /path/to/jpdasm-fork --baseline

# Add --verify to run the base-edit regression check after deploying.
```

Then build on the target:

```bash
cd /path/to/jpdasm-fork
./build_english_rom.sh --jp-rom JP1.0.sfc --us-rom US.sfc     # -> alttp_english.sfc
```

## Isolated review diff (two commits on the target)

To show a reviewer **only** the surgical base-assembly changes — the
function-repointing hooks — cleanly separated from the bulk of relocated code,
make two commits on the target and diff them.

1. **Baseline commit** — everything deployed, base banks left pristine:

   ```bash
   ./apply.sh --target FORK --baseline
   cd FORK && git add -A && git commit -m "English graft: generated code (baseline, no base edits)"
   ```

2. **Changes commit** — the hooks applied, on a new branch:

   ```bash
   git checkout -b english-base-edits
   cd PATCHER && ./apply.sh --target FORK
   cd FORK && git add -A && git commit -m "English graft: apply base-assembly hooks"
   ```

3. **Diff** — confined to the base-bank hooks and the generated-code edits;
   `main.asm` is identical on both sides, so it does not clutter it:

   ```bash
   git diff <baseline-branch>..english-base-edits
   ```

`apply.sh` reads the pristine banks from `.deps/jpdasm` every run and writes the
result into the target, so re-running (or the changes step after the baseline
step) always starts from a known-pristine base.

## Verifying

* **`python3 scripts/verify_base.py --src .deps/jpdasm`** — applies the base
  hooks to the pristine JP and checks each bank's assembler-relevant signature
  against the frozen hashes in `scripts/reference_hashes.txt` (comments ignored,
  since they do not affect assembly). Regenerate the frozen set after an
  intentional change with `--freeze`.
* **`./checks`** — format, type-check, lint, dead-code-scan `scripts/*.py`.
* **End-to-end** — `build_english_rom.sh` prints the built ROM's md5 and flags a
  mismatch against the known-good reference build.
