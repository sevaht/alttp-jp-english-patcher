from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from importlib import resources
from typing import TYPE_CHECKING

from alttp_jp_english_patcher.application import _deploy_tooling
from alttp_jp_english_patcher.generate import (
    _resource_lines,
    _save_migration_lines,
)
from alttp_jp_english_patcher.snes_assembly_parser import Assembly
from alttp_jp_english_patcher.us_assets import (
    US_ASSETS,
    US_ROM_MD5,
    render_binextract_us,
)
from alttp_jp_english_patcher.verify_base import BASE_BANKS, _reference_text

if TYPE_CHECKING:
    from pathlib import Path


def test_save_migration_asm_is_bundled_and_parses() -> None:
    lines = _save_migration_lines()
    assert lines, "save_migration.asm resource is empty/missing"
    text = "\n".join(lines)
    # entry points the boot hook + migrator reach
    for label in ("MigrateAtBoot:", "MigrateSaveSlots:", "JPLatinToWord:"):
        assert label in text
    # it must be valid enough to build an Assembly without raising
    assert Assembly.from_content(lines).lines


def test_usfs_palette_load_asm_is_bundled_and_parses() -> None:
    lines = _resource_lines("usfs_palette_load.asm")
    assert lines, "usfs_palette_load.asm resource is empty/missing"
    text = "\n".join(lines)
    for label in ("USFS_PaletteLoadForFileSelect:", ".row5", ".row11"):
        assert label in text
    assert "USFS_Palette" in text  # the incbin'd data it overlays
    assert Assembly.from_content(lines).lines


def test_title_screen_asm_is_bundled_and_parses() -> None:
    lines = _resource_lines("title_screen.asm")
    assert lines, "title_screen.asm resource is empty/missing"
    text = "\n".join(lines)
    # the genuinely hand-written pieces (everything else is pulled by name
    # in title_screen(), see generate.py)
    for label in (
        "TitleScreenUS_DrawTriangle:",
        "TitleScreenUS_LoadAllPalettes:",
        "TitleScreenUS_AttractInitializePalettes:",
        "Module00_Intro_Dispatch:",
    ):
        assert label in text
    # splice markers title_screen() locates by substring -- a silent rename
    # here should fail a test, not surface only at deploy time
    for marker in (
        "[PULLED] .rightside_objects",
        "[PULLED] US Attract_Initialize's own palette-loading prefix",
    ):
        assert marker in text
    assert Assembly.from_content(lines).lines


def test_reference_hashes_resource_covers_every_base_bank() -> None:
    text = _reference_text()
    for bank in BASE_BANKS:
        assert f"{bank}:" in text


def test_deploy_files_are_bundled() -> None:
    # binextract-us.py is NOT a static deploy file: it is generated from
    # us_assets.US_ASSETS (see test_render_binextract_us_* below), so its
    # (offset, size, md5) data can never drift from generate.py's incbin
    # sizing -- both read the same table.
    root = resources.files("alttp_jp_english_patcher").joinpath("deploy")
    names = (
        "binextract.py",
        "_build.sh",
        "Makefile",
        "_build.bat",
        "README.md",
    )
    for name in names:
        assert root.joinpath(name).is_file()


def test_makefile_and_build_bat_target_the_english_rom() -> None:
    # jpdasm's own Makefile/_build.bat reassemble unmodified JP 1.0 as
    # alttp_reasm.sfc with the checksum fix off; our overrides must instead
    # produce alttp-english.sfc with the checksum fixed (our ROM's contents
    # differ from JP 1.0, so an unfixed checksum would be wrong).
    root = resources.files("alttp_jp_english_patcher").joinpath("deploy")
    for name in ("Makefile", "_build.bat"):
        text = root.joinpath(name).read_text(encoding="utf-8")
        assert "alttp-english.sfc" in text
        assert "alttp_reasm.sfc" not in text
        assert "--fix-checksum=on" in text
        assert "--fix-checksum=off" not in text


def test_deploy_tooling_makes_scripts_executable(tmp_path: Path) -> None:
    # binextract.py and _build.sh are meant to be run directly
    # (`./binextract.py`, `./_build.sh`); write_bytes() doesn't carry over
    # the source's executable bit, so _deploy_tooling must chmod them.
    _deploy_tooling(tmp_path)
    for name in ("binextract.py", "_build.sh"):
        assert os.access(tmp_path / name, os.X_OK), f"{name} not executable"


def test_render_binextract_us_is_valid_python() -> None:
    text = render_binextract_us()
    ast.parse(text)  # raises SyntaxError if malformed
    # one ASSETS row per US_ASSETS entry, in the same order, agreeing values
    for a in US_ASSETS:
        assert f"{a.filename!r}" in text
        assert f"{a.md5!r}" in text
        for s in a.slices:
            assert f"{s.offset:#x}" in text
            assert f"{s.length:#x}" in text


def test_render_binextract_us_extracts_from_a_synthetic_rom(
    tmp_path: Path,
) -> None:
    # a big-enough synthetic "ROM": each byte equals its own low byte, so
    # every slice's content -- and thus its md5 -- is deterministic and
    # independent of the real US ROM (this only proves the GENERATED
    # SCRIPT's own slicing/plumbing is correct, not that the real offsets
    # are right -- that is proven by generate.py's actual build against a
    # real ROM elsewhere).
    size = max(s.offset + s.length for a in US_ASSETS for s in a.slices) + 1
    rom = bytes(i & 0xFF for i in range(size))
    rom_path = tmp_path / "alttp-us.sfc"
    rom_path.write_bytes(rom)

    def digest(data: bytes) -> str:
        # matches the identity check the ROMs/assets use -- not a security
        # context, hence usedforsecurity=False (satisfies ruff's S324).
        return hashlib.md5(data, usedforsecurity=False).hexdigest()

    # patch the generated script's md5 checks to match our synthetic ROM/
    # assets, so it runs end-to-end without needing the real copyrighted ROM
    text = render_binextract_us()
    text = text.replace(repr(US_ROM_MD5), repr(digest(rom)))
    for a in US_ASSETS:
        data = b"".join(rom[s.offset : s.offset + s.length] for s in a.slices)
        text = text.replace(repr(a.md5), repr(digest(data)))
    script = tmp_path / "binextract-us.py"
    script.write_text(text)

    subprocess.run(  # noqa: S603 -- the just-written, fully-controlled script
        [sys.executable, str(script), "--us-rom", str(rom_path)],
        check=True,
        capture_output=True,
    )
    for a in US_ASSETS:
        out = tmp_path / "bin" / "gfx" / a.filename
        expected = b"".join(
            rom[s.offset : s.offset + s.length] for s in a.slices
        )
        assert out.read_bytes() == expected


def test_ensure_anchors_labels_bare_lines_with_pc() -> None:
    # ensure_anchors gives label-less instruction/data lines the #_<hex>
    # per-line address labels the disassembly convention wants; render(org)
    # re-stamps them to the running PC (advancing by each line's size).
    asm = Assembly.from_content(
        ["Foo:", "PHY", "JSR Bar", ".sub", "dw $0000, $0001"]
    )
    rendered = asm.ensure_anchors().render(0x2C8000).splitlines()
    joined = "\n".join(rendered)
    assert "#_2C8000: PHY" in joined  # 1 byte
    assert "#_2C8001: JSR Bar" in joined  # +3 bytes
    assert "#_2C8004: dw $0000, $0001" in joined  # .sub is size 0
    assert "Foo:" in rendered  # top-level label untouched
    assert ".sub" in rendered  # sublabel untouched
