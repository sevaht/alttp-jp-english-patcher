"""Generate a patched (English) jpdasm into a target directory (the CLI).

The ``--target`` is treated as an *output* directory, not an existing checkout:
it is created if missing, and any files this produces are overwritten if it
exists (anything else -- your ROMs, extracted binaries, built ROM -- is left
alone). So every run starts from the pristine disassemblies and is fully
predictable/repeatable.

Each run: clones (or reuses) pristine ``usdasm`` + ``jpdasm``; copies the JP
disassembly's support files (``asarmon.exe``, the reference ``.asm``, ``bin/``
dirs, ``binextract.py`` -> ``binextract-jp.py``) into the target; writes the
whole English program over it (base banks hooked in place, graft banks beside
them, ``main.asm`` wired); drops in the build tooling (``binextract-us.py`` +
the ``binextract.py`` stub + build script + README) and the ``.gitignore``; and
copies the two ROMs into place (``alttp.sfc`` / ``alttp-us.sfc``) if given.

The two disassembly *sources* are plain git checkouts, cloned on demand into
the platformdirs user cache (see
:func:`~alttp_jp_english_patcher.user_cache_path`); override with ``--usdasm``
/ ``--jpdasm`` or ``USDASM_DIR`` / ``JPDASM_DIR``.
"""

from __future__ import annotations

import argparse
import os
import shutil
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


# ROMs the target needs: (destination filename, args attr, --flag).
_ROMS = (
    ("alttp.sfc", "jp_rom", "--jp-rom"),
    ("alttp-us.sfc", "us_rom", "--us-rom"),
)


def _populate_from_jpdasm(jpdasm: Path, target: Path) -> None:
    """Fill ``target`` with the pristine jpdasm's support files.

    Copies everything except its git metadata and its own ``binextract.py``
    (which becomes ``binextract-jp.py``); the generated ``.asm`` files are
    overwritten by :meth:`Rom.write` right after. ``asarmon.exe``, the
    reference ``.asm``, the ``bin/`` directory scaffolding, ``Makefile`` /
    ``_build.bat``, and ``LICENSE`` come along so the target is a
    self-contained buildable fork.
    """
    ignore = shutil.ignore_patterns(
        ".git", ".github", "__pycache__", "binextract.py"
    )
    shutil.copytree(jpdasm, target, dirs_exist_ok=True, ignore=ignore)
    jp_extractor = jpdasm / "binextract.py"
    if jp_extractor.is_file():
        shutil.copy2(jp_extractor, target / "binextract-jp.py")


def _deploy_tooling(target: Path) -> None:
    """Drop the English build tooling into the target (overwriting)."""
    root = resources.files("alttp_jp_english_patcher").joinpath("deploy")
    for name in _DEPLOY_FILES:
        (target / name).write_bytes(root.joinpath(name).read_bytes())
    (target / "build_english_rom.sh").chmod(0o755)


def _place_roms(target: Path, args: argparse.Namespace) -> None:
    """Copy any supplied ROMs into the target under their expected names."""
    for dest_name, attr, _flag in _ROMS:
        source = getattr(args, attr)
        if source is not None:
            shutil.copy2(source, target / dest_name)
            print(f"copied {source} -> {dest_name}")


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
        description="Generate a patched (English) jpdasm into a directory.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="output directory (created if missing; our files overwritten)",
    )
    parser.add_argument(
        "--jp-rom",
        type=Path,
        help="JP 1.0 ROM, copied in as alttp.sfc (required if not already "
        "in the target)",
    )
    parser.add_argument(
        "--us-rom",
        type=Path,
        help="US ROM, copied in as alttp-us.sfc (required if not already "
        "in the target)",
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

    # fail fast if a ROM is neither supplied nor already present
    for dest_name, attr, flag in _ROMS:
        source = getattr(args, attr)
        if source is not None and not source.is_file():
            parser.error(f"{flag} {source} not found")
        if source is None and not (target / dest_name).is_file():
            parser.error(f"{dest_name} is not in the target; pass {flag}")

    usdasm = _resolve_source("usdasm", args.usdasm, "USDASM_DIR")
    jpdasm = _resolve_source("jpdasm", args.jpdasm, "JPDASM_DIR")

    print(f"==> generating a patched jpdasm -> {target}")
    target.mkdir(parents=True, exist_ok=True)
    _populate_from_jpdasm(jpdasm, target)
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
    _place_roms(target, args)

    if args.verify:
        print("==> verifying base edits")
        if _run_verify(jpdasm, usdasm) != 0:
            return 1

    print("\nDone.\n")
    print(f"In {target} run these commands:")
    print("  python3 binextract.py")
    print("  ./build_english_rom.sh")
    return 0
