# alttp-jp-english-patcher

Generator/toolkit that turns a **pristine fork of
[spannerisms/jpdasm](https://github.com/spannerisms/jpdasm)** (the *A Link to
the Past* JP 1.0 disassembly) into a **functional English translation** — by
grafting in the US ROM's English text/menu/graphics subsystems.

All the generative machinery lives here as a proper Python package. Running the
`alttp-jp-english-patcher` command **generates a patched (English) jpdasm into an
output directory** — always starting from the pristine disassemblies, so every
run is fully predictable and repeatable. The `--target` is treated as an output
directory: it is created if missing, and the files this produces are overwritten
if it exists (your ROMs, extracted binaries, and built ROM are left alone).

```
  this package                                 --target (output directory)
  ┌──────────────────────┐  alttp-jp-        ┌───────────────────────────┐
  │ src/alttp_jp_english_│  english-patcher  │ bank_00..bank_1F  (hooked) │ base
  │   patcher/           │ ─────────────────▶│ bank_20..bank_2E  (graft)  │ graft
  │   generate · graft   │                   │ main.asm  asarmon.exe      │ + jpdasm
  │   verify_base        │  clones usdasm +  │ binextract{,-jp,-us}.py    │   support
  │   resources · deploy │  jpdasm to cache  │ build_english_rom.sh       │ + build tool
  └──────────────────────┘                   │ alttp.sfc  alttp-us.sfc    │ + your ROMs
                                             └───────────────────────────┘
```

## Quick start

```bash
uv sync                                   # install the package + its deps
# Generate the patched jpdasm (ROMs are copied in; you own both, nothing here
# is copyrighted):
uv run alttp-jp-english-patcher --target ./alttp-jp-english \
    --jp-rom YOUR_JP1.0.sfc --us-rom YOUR_US.sfc
# Then extract the ROM-derived binaries and build, in the target:
cd ./alttp-jp-english
python3 binextract.py           # extract bin/* (JP) and english/* (US)
./build_english_rom.sh          # -> alttp-english.sfc
```

`--jp-rom` / `--us-rom` are copied in as `alttp.sfc` / `alttp-us.sfc`, and are
only required if those files aren't already in the target (so later runs can
omit them). The command clones the two disassembly *sources* it reads from
(`spannerisms/usdasm`, a pristine `jpdasm`) into the platformdirs user cache
(e.g. `~/.cache/alttp-jp-english-patcher/{usdasm,jpdasm}`); override with
`--usdasm` / `--jpdasm` or `USDASM_DIR` / `JPDASM_DIR`.

## What it puts in the target

| Step | Result in the target |
| --- | --- |
| Populate from jpdasm | the pristine JP disassembly's support files: `asarmon.exe`, the reference `.asm`, the `bin/` scaffolding, `Makefile`/`_build.bat`, `LICENSE`; its own `binextract.py` becomes `binextract-jp.py` |
| Generate the whole program | base `bank_00/0C/0D/0E/13/18/1C/1D.asm` hooked in place; graft `bank_20/22/23/26/27/2C/2D/2E.asm` beside them; `main.asm` wired (`bank_2X` includes + 2 MB padding); every untouched unit round-tripped |
| Deploy tooling | `binextract-us.py` (US assets), a `binextract.py` stub that runs both extractors, `build_english_rom.sh`, an English `README.md`, and `.gitignore` rules for the ROM-derived `english/*` blobs |
| Copy ROMs | any supplied `--jp-rom` / `--us-rom` land as `alttp.sfc` / `alttp-us.sfc` |

## Layout

```
src/alttp_jp_english_patcher/
  __main__.py · application.py  the CLI (deploy orchestration)
  generate.py                   the whole program: build() on one Rom -- every
                                subsystem (text/menu/item-menu/credits/font/
                                graphics/palette) declares what it hooks
  graft.py                      relocation + EN_ namespacing + hook/pad decls
  gitignore.py                  target .gitignore patcher
  verify_base.py                regression guard (frozen hashes)
  snes_assembly_parser/         the vendored parser library (its own tests
                                live under tests/snes_assembly_parser/)
  resources/
    save_migration.asm          the boot-time save migrator (65816 source)
    reference_hashes.txt         expected base-edit signatures
  deploy/                       files written verbatim into the target
    binextract-us.py            US ROM-derived asset extractor
    binextract.py               stub: runs binextract-jp.py + binextract-us.py
    build_english_rom.sh        one-command target build (assemble only)
    README.md                   the target's English-build README
tests/  checks  pyproject.toml  standard package tooling (needs uv)
```

Embedded resources (`resources/`, `deploy/`) are read via
`importlib.resources`, never as on-disk paths.

## Development

* `./checks` — format, type-check, lint, dead-code-scan, and run the tests
  (needs `uv`).
* `uv run python -m alttp_jp_english_patcher.verify_base --src JPDASM --usdasm USDASM`
  — confirm the generated base banks still reproduce the frozen reference
  signatures (or `alttp-jp-english-patcher --target ... --verify`).

See **[GENERATION.md](GENERATION.md)** for the full workflow and the two-commit
process that produces an isolated, reviewable diff of the base assembly changes.
