#!/usr/bin/env python3
"""Regression guard for :mod:`base_edits`.

Applies the base-bank hooks to a pristine jpdasm checkout and compares each
hooked bank's *assembler-relevant signature* (label|opcode|args per content
line -- comments and blank lines ignored, since they do not affect assembly)
against a frozen hash in ``reference_hashes.txt``. A mismatch means either the
edits changed or an upstream bank drifted; a clean run means the generated
hooks still reproduce the reviewed result.

    python3 verify_base.py --src /path/to/pristine/jpdasm
    python3 verify_base.py --src ... --freeze   # (re)write the reference
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

from snes_assembly_parser import Assembly

from base_edits import apply_all

REFERENCE = Path(__file__).with_name("reference_hashes.txt")


def signature_hash(path: Path) -> str:
    """SHA-256 of a bank's content-line signature (comments/blanks ignored)."""
    lines = [
        f"{line.label or ''}|{line.opcode or ''}|{','.join(line.arguments)}"
        for line in Assembly.from_path(path).lines
        if line.has_content
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def compute(src: Path) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        banks = apply_all(src, Path(temp_dir))
        return {
            bank: signature_hash(Path(temp_dir) / f"{bank}.asm")
            for bank in banks
        }


def load_reference() -> dict[str, str]:
    reference: dict[str, str] = {}
    for raw in REFERENCE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        bank, digest = line.split(":", 1)
        reference[bank.strip()] = digest.strip()
    return reference


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src", type=Path, required=True, help="pristine jpdasm checkout"
    )
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="write current hashes to reference_hashes.txt, don't check",
    )
    args = parser.parse_args()
    if not args.src.exists():
        print(f"error: pristine jpdasm {args.src} not found", file=sys.stderr)
        return 2

    got = compute(args.src)
    if args.freeze:
        body = "".join(f"{bank}: {got[bank]}\n" for bank in sorted(got))
        REFERENCE.write_text(
            "# base_edits.py bank-signature hashes (see verify_base.py)\n"
            + body
        )
        print(f"froze {len(got)} hashes to {REFERENCE.name}")
        return 0

    reference = load_reference()
    mismatched = []
    for bank in sorted(got):
        if got[bank] == reference.get(bank):
            print(f"  {bank}: match")
        else:
            print(f"  {bank}: MISMATCH")
            mismatched.append(bank)
    if mismatched:
        print(f"FAIL: {', '.join(mismatched)}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
