# alttp-jp-1.0-english-patcher

Generator/toolkit that turns a **pristine fork of
[spannerisms/jpdasm](https://github.com/spannerisms/jpdasm)** (the *A Link to
the Past* JP 1.0 disassembly) into a **functional English translation** — by
grafting in the US ROM's English text/menu/graphics subsystems.

All the generative machinery lives here. Running it deploys a clean result into
the target disassembly, so that repository stays free of this generator's noise:
it ends up with just the hooked base banks, the graft's `bank_20`..`bank_2E`
banks beside them, and the build tooling.

```
  this repo (patcher)                         target repo (jpdasm fork)
  ┌───────────────────┐   ./apply.sh          ┌───────────────────────────┐
  │ scripts/ (7 gens) │  ── --target ───────▶ │ bank_00..bank_1F  (hooked) │ base
  │ apply.sh          │                        │ bank_20..bank_2E  (graft)  │ deployed
  │ extract/build     │   fetches usdasm +     │ main.asm                   │ patched
  │                   │   jpdasm + parser lib  │ extract_english_assets.py  │ + build tool
  └───────────────────┘   into .deps/          └───────────────────────────┘
```

## Quick start

```bash
# Deploy the graft into your jpdasm fork, then build the ROM.
./apply.sh --target /path/to/alttp-jp-1.0-english --us-rom US.sfc --jp-rom JP1.0.sfc
cd /path/to/alttp-jp-1.0-english
./build_english_rom.sh --jp-rom JP1.0.sfc --us-rom US.sfc   # -> alttp_english.sfc
```

`apply.sh` fetches everything it needs into `.deps/` (gitignored): the parser
library, the US disassembly it pulls text from, and a pristine JP disassembly it
uses as the hook source. You provide the two ROMs you own (nothing copyrighted
is stored here — the ROM-derived binaries are regenerated on the target).

See **[GENERATION.md](GENERATION.md)** for the full workflow, including the
two-commit process that produces an isolated, reviewable diff of the base
assembly changes.

## What it does to the target

| Step | Script | Result in the target |
| --- | --- | --- |
| Generate the whole program | `scripts/generate.py` | base `bank_00/0C/0D/0E/13/18/1C.asm` hooked in place; graft `bank_20/22/23/26/27/2C/2D/2E.asm` beside them; `main.asm` wired (`bank_2X` includes + 2 MB padding); every untouched unit round-tripped |
| Deploy tooling | `apply.sh` | `extract_english_assets.py` + `build_english_rom.sh` |
| Ignore binaries | `scripts/gitignore.py` | `.gitignore` excludes the ROM-derived `english/*` blobs |

## Layout

```
apply.sh                     the one entry point (orchestrator)
scripts/                     the generator toolkit
  graft.py                   relocation + EN_ namespacing + hook/pad decls
  generate.py                the whole program: build() on one Rom -- every
                             subsystem (text/menu/item-menu/credits/font/
                             graphics/palette) declares what it hooks;
                             _wire_hooks derives frees + alias-or-pad from
                             the program's callers (Rom.needs_landing_pad)
  gitignore.py               target .gitignore patcher
  verify_base.py             regression guard (frozen hashes)
  reference_hashes.txt       expected base-edit signatures
extract_english_assets.py    ROM-derived binary extractor (deployed to target)
build_english_rom.sh         one-command target build (deployed to target)
checks  pyproject.toml       lint/typecheck the scripts (needs uv)
```

## Development

* `./checks` — format, type-check, lint, dead-code-scan `scripts/*.py` (needs
  `uv`; run `./apply.sh` once first, or set `SNES_PARSER_DIR`).
* `python3 scripts/verify_base.py --src .deps/jpdasm --usdasm .deps/usdasm` —
  confirm the generated base banks still reproduce the frozen reference
  signatures.
