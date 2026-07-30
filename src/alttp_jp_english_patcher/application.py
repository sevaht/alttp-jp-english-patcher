"""Deploy the English graft into a pristine jpdasm fork (the CLI).

Generates the whole English program from pristine usdasm + jpdasm checkouts and
writes it into a target fork: base banks hooked in place, graft banks beside
them, ``main.asm`` wired. Then it drops in the build tooling (the
``binextract`` extractors + build script + README) and updates ``.gitignore``.

The parser library (``snes-assembly-parser``) is an installed dependency. The
two disassembly *sources* are plain git checkouts, cloned on demand into the
user cache (override with ``--usdasm`` / ``--jpdasm`` or ``USDASM_DIR`` /
``JPDASM_DIR``).
"""

from __future__ import annotations

import argparse
import os
import subprocess
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from . import user_cache_path, verify_base
from .generate import build
from .gitignore import patch as patch_gitignore
from .graft import bank_header

if TYPE_CHECKING:
    from collections.abc import Sequence

# disassembly sources: label -> (git url, ref, a file that marks a good clone).
_SOURCES = {
    "usdasm": (
        "https://github.com/spannerisms/usdasm.git",
        "main",
        "bank_0E.asm",
    ),
    "jpdasm": (
        "https://github.com/spannerisms/jpdasm.git",
        "master",
        "bank_00.asm",
    ),
}

# bundled deploy artifacts -> written verbatim into the target fork.
_DEPLOY_FILES = (
    "binextract-us.py",
    "binextract.py",
    "build_english_rom.sh",
    "README.md",
)


def _clone(label: str, dest: Path) -> None:
    """Clone the ``label`` source into ``dest`` if missing; else leave it."""
    url, ref, sentinel = _SOURCES[label]
    if (dest / sentinel).exists():
        print(f"{label}: using existing {dest}")
        return
    print(f"{label}: cloning ({ref})")
    command = ["git", "clone", "--quiet", "--depth", "1", "--branch", ref]
    command += [url, str(dest)]
    subprocess.run(command, check=True)  # noqa: S603
    if not (dest / sentinel).exists():
        msg = f"{dest / sentinel} missing after clone"
        raise RuntimeError(msg)


def _resolve_source(label: str, override: Path | None, env_var: str) -> Path:
    """A --flag override / $ENV path (used as-is), else a cached clone."""
    if override is not None:
        return override.resolve()
    env = os.environ.get(env_var)
    if env:
        return Path(env).resolve()
    dest = user_cache_path() / label
    dest.parent.mkdir(parents=True, exist_ok=True)
    _clone(label, dest)
    return dest


def _deploy_tooling(target: Path) -> None:
    """Rename the base JP extractor and drop in the English build tooling."""
    jp_extractor = target / "binextract.py"
    renamed = target / "binextract-jp.py"
    if jp_extractor.exists() and not renamed.exists():
        jp_extractor.rename(renamed)
    root = resources.files("alttp_jp_english_patcher").joinpath("deploy")
    for name in _DEPLOY_FILES:
        (target / name).write_bytes(root.joinpath(name).read_bytes())
    (target / "build_english_rom.sh").chmod(0o755)


def _update_gitignore(target: Path) -> None:
    path = target / ".gitignore"
    original = path.read_text() if path.exists() else ""
    patched = patch_gitignore(original)
    if patched != original:
        path.write_text(patched)
        print(f"{path}: added English binary ignore rules")


def _run_verify(jpdasm: Path, usdasm: Path) -> int:
    got = verify_base.compute(jpdasm, usdasm)
    reference = verify_base.load_reference()
    mismatched = [b for b in sorted(got) if got[b] != reference.get(b)]
    for bank in sorted(got):
        print(f"  {bank}: {'MISMATCH' if bank in mismatched else 'match'}")
    if mismatched:
        print(f"FAIL: {', '.join(mismatched)}")
        return 1
    print("base edits OK")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alttp-jp-english-patcher",
        description="Deploy the English graft into a jpdasm fork.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="the jpdasm fork to write the English program into",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="emit the change-free baseline (no graft edits or base hooks)",
    )
    parser.add_argument(
        "--no-save-compatibility",
        action="store_true",
        help="omit the boot-time US/Japanese save-slot migrator",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="after deploying, check the base edits against the frozen hashes",
    )
    parser.add_argument(
        "--usdasm", type=Path, help="US disassembly checkout (default: cached)"
    )
    parser.add_argument(
        "--jpdasm", type=Path, help="JP disassembly checkout (default: cached)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    target = args.target.resolve()
    if (
        not (target / "bank_00.asm").is_file()
        or not (target / "main.asm").is_file()
    ):
        parser.error(f"{target} does not look like a jpdasm checkout")

    usdasm = _resolve_source("usdasm", args.usdasm, "USDASM_DIR")
    jpdasm = _resolve_source("jpdasm", args.jpdasm, "JPDASM_DIR")

    print(f"==> generating the English program -> {target}")
    english = build(
        usdasm=usdasm,
        jpdasm=jpdasm,
        changes=not args.baseline,
        save_compat=not args.no_save_compatibility,
    )
    english.write(target, bank_header=bank_header)

    print("==> deploying build tooling")
    _deploy_tooling(target)
    _update_gitignore(target)

    if args.verify:
        print("==> verifying base edits")
        if _run_verify(jpdasm, usdasm) != 0:
            return 1

    print(
        f"done. In {target}: place alttp.sfc + alttp-us.sfc, run "
        "`python3 binextract.py`, then `./build_english_rom.sh`."
    )
    return 0
