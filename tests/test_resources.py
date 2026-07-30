from __future__ import annotations

from importlib import resources

from snes_assembly_parser import Assembly

from alttp_jp_english_patcher.generate import _save_migration_lines
from alttp_jp_english_patcher.verify_base import BASE_BANKS, _reference_text


def test_save_migration_asm_is_bundled_and_parses() -> None:
    lines = _save_migration_lines()
    assert lines, "save_migration.asm resource is empty/missing"
    text = "\n".join(lines)
    # entry points the boot hook + migrator reach
    for label in ("MigrateAtBoot:", "MigrateSaveSlots:", "JPLatinToWord:"):
        assert label in text
    # it must be valid enough to build an Assembly without raising
    assert Assembly.from_content(lines).lines


def test_reference_hashes_resource_covers_every_base_bank() -> None:
    text = _reference_text()
    for bank in BASE_BANKS:
        assert f"{bank}:" in text


def test_deploy_files_are_bundled() -> None:
    root = resources.files("alttp_jp_english_patcher").joinpath("deploy")
    for name in (
        "binextract.py",
        "binextract-us.py",
        "build_english_rom.sh",
        "README.md",
    ):
        assert root.joinpath(name).is_file()
