#!/usr/bin/env python3
"""Extract every ROM-derived binary the English build needs.

The English translation draws binaries from TWO ROMs, so extraction is split:

  * binextract-jp.py             -- the base disassembly's own extractor
                                    (graphics/audio from the JP 1.0 ROM,
                                    named `alttp.sfc`)
  * binextract-us.py             -- the English font/menu assets (from the
                                    US ROM, named `alttp-us.sfc`)
  * binextract-jp-credits-font.py        -- the credits' bold font, decompressed
                                    offline from the JP 1.0 ROM (no
                                    emulator; a plain from-ROM-bytes
                                    algorithm) into a flat sheet
  * binextract-us-credits-font.py -- a US-styled alternate for that same
                                    font (--credits-font us), same tile
                                    layout, pixel data pulled from the US
                                    dialogue font instead

This stub just runs all four (only the credits font matching your
--credits-font choice at generation time actually ends up `incbin`'d --
extracting the other one too is harmless, just unused). Place both ROMs in
this directory first:
    alttp.sfc      JP 1.0 (md5 03a63945398191337e896e5771f77173)
    alttp-us.sfc   US     (md5 608c22b8ff930c62dc2de54bcd6eba72)

Then:  python3 binextract.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

_SCRIPTS = (
    "binextract-jp.py",
    "binextract-us.py",
    "binextract-jp-credits-font.py",
    "binextract-us-credits-font.py",
)


def main() -> int:
    for script in _SCRIPTS:
        print(f"==> {script}")
        subprocess.run([sys.executable, str(HERE / script)], check=True)
    print("\nAll binaries extracted. Build with ./_build.sh (or make/_build.bat)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
