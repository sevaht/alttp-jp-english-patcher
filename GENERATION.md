# Generating the English translation

This repo is the **generator**. It transforms a pristine fork of
[spannerisms/jpdasm](https://github.com/spannerisms/jpdasm) into a functional
English build, keeping that fork clean of the generator itself. This document
explains what is produced, how to run it, and how to produce an isolated review
diff of the base-assembly changes.

## The two repositories

* **This repo (patcher)** — the `alttp_jp_english_patcher` Python package: the
  generator toolkit plus the `deploy/` files it drops into the target. The
  `alttp-jp-english-patcher` console command runs it.
* **The target (`--target` output directory)** — a generated jpdasm fork. After
  the command it is a functional English translation: the base banks hooked in
  place, the graft's expanded-ROM banks `bank_20.asm` .. `bank_2E.asm` sitting
  beside them, a patched `main.asm`, the JP disassembly's support files, and the
  build tooling. None of this generator is copied into it.

The hook source is always a freshly-cloned **pristine** `jpdasm` (in the user
cache), never the target itself. The target is populated from that pristine copy
each run, so the base banks are always derived from a known-pristine base and
re-running is safe (it never hooks an already-hooked bank).

## What is produced

The graft is emitted as `bank_XX.asm` files -- one per expanded-ROM bank,
following the disassembly's own convention -- so the fork reads `bank_00` ..
`bank_1F` (base) then `bank_20` .. `bank_2E` (graft):

| Output in the target | Produced by | From |
| --- | --- | --- |
| `bank_00/0C/0D/0E/13/18/1C.asm` hooks | `generate.py` | `jpdasm` (pristine) |
| `bank_20.asm` (VWF font + `TransferFontToVRAM`) | `generate.py` | `jpdasm` + `usdasm` |
| `bank_22.asm` / `bank_23.asm` (message data) | `generate.py` | `usdasm` |
| `bank_2C.asm` (file-select) | `generate.py` | `usdasm` + `jpdasm` |
| `bank_2D.asm` (item menu) | `generate.py` | `usdasm` + `jpdasm` |
| `bank_2E.asm` (text engine + credits) | `generate.py` | `usdasm` + `jpdasm` |
| `bank_26.asm` (US graphics sheets) | `generate.py` | `usdasm` (via incbin) |
| `bank_27.asm` (file-select palette) | `generate.py` | `usdasm` (via incbin) |
| `main.asm` includes + 2 MB padding | `generate.py` | — |
| the untouched base banks + `main`/`functions`/`registers` | `generate.py` | `jpdasm` (round-tripped) |
| `asarmon.exe`, reference `.asm`, `bin/` dirs, `Makefile`, `LICENSE`; `binextract.py` → `binextract-jp.py` | copied | `jpdasm` (pristine) |
| `.gitignore` binary excludes | `gitignore.py` | — |
| `binextract-us.py`, `binextract.py` stub, `build_english_rom.sh`, `README.md` | deployed | — |
| `alttp.sfc` / `alttp-us.sfc` | copied | `--jp-rom` / `--us-rom` |

`generate.py` does it all in one pass: it loads the pristine JP disassembly as
a single whole-program `Rom`, folds every relocated subsystem into it (each a
self-contained function whose placed, org-addressed pieces get grouped by ROM
bank -- no subsystem owns a file, the bank does), hooks the base banks to reach
them, wires `main.asm`, and writes the entire fork back out (the hooked base
banks, the graft banks beside them, and every untouched unit round-tripped
byte-for-byte).

The ROM-derived binaries (`english/font.2bpp`, `*.2bppc`, `*.3bppc`,
`usfs_pal.bin`) are **not** stored anywhere — they are copyrighted game data.
They are regenerated on the target from your US ROM by `binextract-us.py`, run
(alongside the base disassembly's `binextract-jp.py`) by the `binextract.py`
stub the deploy drops in.

* **`generate.py`** does everything on one whole-program `Rom`:
  * **`build()`** loads the pristine US and JP, `add`s every relocated
    subsystem, wires the hooks + the few non-hook base edits + `main.asm`, and
    returns the `Rom`; `Rom.write` emits the fork.
  * **the subsystem functions** (`text`, `font_upload`, `credits_bank`,
    `item_menu`, `file_select`, `graphics`, `file_select_palette`) relocate
    each subsystem into the expanded ROM (2nd MB) under the `EN_` namespace,
    pulling what they need *by name* from the US and/or JP disassembly and
    applying the documented English edits (no hand-maintained relocated
    assembly). Each also **declares what it hooks**: the entry-point names in
    `hooked`, and the blocks it carries in `relocated` — not *how* each is
    reached. `Rom.write` regroups the placed pieces into the per-bank
    `bank_2X.asm` files.
  * **`_wire_hooks()`** applies the base half of every hook, *derived from the
    relocations and the program's callers*. It frees each hooked JP name
    (`UNREACHABLE_` rename) and, per name, uses `Rom.needs_landing_pad` to decide
    how the bare name is re-claimed: a same-bank caller that stays behind (not in
    the relocation's `relocated` set) gets a register-transparent `JSL EN_name /
    RTS` landing pad; otherwise the relocated copy's bare alias suffices. The
    driver never states which — it falls out of who calls what.
  * **`apply_base_edits()`** adds the few edits that are *not* plain hooks: one
    inline-block `JML` redirect (the V-IRQ handler), a few byte-neutral operand
    swaps, one re-pinned data `org`, one live reference kept on the original —
    all located by label/`#_` anchor (never a line number), so an edit fails
    loud if upstream drifts.

## Prerequisites

* `uv` (installs the package + its dependencies, including the parser library).
* `git` (the command clones the disassembly sources it reads).
* Two ROMs you own (copied into the target as `alttp.sfc` / `alttp-us.sfc`):
  * JP 1.0 — md5 `03a63945398191337e896e5771f77173`
  * US — md5 `608c22b8ff930c62dc2de54bcd6eba72`

The command clones `usdasm` (spannerisms, `main`) and `jpdasm` (spannerisms,
`master`) into the platformdirs user cache if missing (on Linux,
`~/.cache/alttp-jp-english-patcher/{usdasm,jpdasm}`). Override either with
`--usdasm` / `--jpdasm` or `USDASM_DIR` / `JPDASM_DIR` (point at an existing
checkout).

The `--target` is an *output directory*: created if missing, and the files the
run produces are overwritten if it exists (your ROMs, extracted binaries, and
built ROM are left alone). It is populated fresh from the pristine `jpdasm` each
run, so re-running is safe and predictable -- the target is never used as its
own hook source.

## Running it

```bash
uv sync                                           # once

# Generate the patched jpdasm (ROMs copied in as alttp.sfc / alttp-us.sfc):
uv run alttp-jp-english-patcher --target ./alttp-jp-english \
    --jp-rom JP1.0.sfc --us-rom US.sfc

# Baseline: the change-free form (no base hooks, baseline graft banks):
uv run alttp-jp-english-patcher --target ./alttp-jp-english --baseline \
    --jp-rom JP1.0.sfc --us-rom US.sfc

# --jp-rom / --us-rom may be omitted once the ROMs are already in the target.
# Add --verify to run the base-edit regression check after generating.
```

Then extract the ROM binaries and build in the target:

```bash
cd ./alttp-jp-english
python3 binextract.py
./build_english_rom.sh                            # -> alttp_english.sfc
```

## Isolated review diff (two commits on the target)

To show a reviewer **only** the surgical base-assembly changes — the
function-repointing hooks — cleanly separated from the bulk of relocated code,
make two commits on the target and diff them.

1. **Baseline commit** — everything generated, base banks left pristine (pass
   the ROMs once; they are gitignored, so they never enter a commit):

   ```bash
   uv run alttp-jp-english-patcher --target FORK --baseline \
       --jp-rom JP1.0.sfc --us-rom US.sfc
   cd FORK && git add -A && git commit -m "English graft: generated code (baseline, no base edits)"
   ```

2. **Changes commit** — the hooks applied, on a new branch (ROMs already in the
   target, so no `--jp-rom` / `--us-rom` needed):

   ```bash
   git checkout -b english-base-edits
   uv run alttp-jp-english-patcher --target FORK
   cd FORK && git add -A && git commit -m "English graft: apply base-assembly hooks"
   ```

3. **Diff** — confined to the base-bank hooks and the generated-code edits;
   `main.asm` is identical on both sides, so it does not clutter it:

   ```bash
   git diff <baseline-branch>..english-base-edits
   ```

The command reads the pristine banks from the cached `jpdasm` every run and
writes the result into the target, so re-running (or the changes step after the
baseline step) always starts from a known-pristine base.

## Verifying

* **`uv run python -m alttp_jp_english_patcher.verify_base --src JPDASM --usdasm USDASM`**
  — applies the base hooks to the pristine JP and checks each bank's
  assembler-relevant signature against the frozen hashes in the
  `reference_hashes.txt` resource (comments ignored, since they do not affect
  assembly). Regenerate the frozen set after an intentional change with
  `--freeze`. (`--target ... --verify` runs the same check after a deploy.)
* **`./checks`** — format, type-check, lint, dead-code-scan, and run the tests.
* **End-to-end** — `build_english_rom.sh` prints the built ROM's md5 and flags a
  mismatch against the known-good reference build.
