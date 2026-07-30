# alttp-jp-english-patcher

Generator/toolkit that turns a **pristine fork of
[spannerisms/jpdasm](https://github.com/spannerisms/jpdasm)** (the *A Link to
the Past* JP 1.0 disassembly) into a **functional English translation** — by
grafting in the US ROM's English text/menu/graphics subsystems.

All the generative machinery lives here as a proper Python package. Running the
`alttp-jp-english-patcher` command deploys a clean result into the target
disassembly, so that repository stays free of this generator's noise: it ends up
with just the hooked base banks, the graft's `bank_20`..`bank_2E` banks beside
them, and the build tooling.

```
  this package                                target repo (jpdasm fork)
  ┌──────────────────────┐  alttp-jp-        ┌───────────────────────────┐
  │ src/alttp_jp_english_│  english-patcher  │ bank_00..bank_1F  (hooked) │ base
  │   patcher/           │ ── --target ────▶ │ bank_20..bank_2E  (graft)  │ deployed
  │   generate · graft   │                   │ main.asm                   │ patched
  │   verify_base        │  clones usdasm +  │ binextract{,-jp,-us}.py    │ + build tool
  │   resources · deploy │  jpdasm to cache  │ build_english_rom.sh       │
  └──────────────────────┘                   └───────────────────────────┘
```

## Quick start

```bash
uv sync                                   # install the package + its deps
# Deploy the graft into your jpdasm fork:
uv run alttp-jp-english-patcher --target /path/to/alttp-jp-english
# Then build the ROM in the target (you own both ROMs; nothing here is copyrighted):
cd /path/to/alttp-jp-english
cp YOUR_JP1.0.sfc alttp.sfc && cp YOUR_US.sfc alttp-us.sfc
python3 binextract.py           # extract the ROM-derived binaries
./build_english_rom.sh          # -> alttp_english.sfc
```

The command clones the two disassembly *sources* it reads from
(`spannerisms/usdasm` for the English text, a pristine `jpdasm` as the hook
source) into the user cache; override with `--usdasm` / `--jpdasm` or
`USDASM_DIR` / `JPDASM_DIR`. The parser library
(`snes-assembly-parser`) is an ordinary installed dependency.

## What it does to the target

| Step | Result in the target |
| --- | --- |
| Generate the whole program | base `bank_00/0C/0D/0E/13/18/1C.asm` hooked in place; graft `bank_20/22/23/26/27/2C/2D/2E.asm` beside them; `main.asm` wired (`bank_2X` includes + 2 MB padding); every untouched unit round-tripped |
| Deploy tooling | renames the base disassembly's `binextract.py` → `binextract-jp.py`; drops in `binextract-us.py` (US assets), a `binextract.py` stub that runs both, `build_english_rom.sh`, and an English `README.md` |
| Ignore binaries | `.gitignore` excludes the ROM-derived `english/*` blobs |

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
