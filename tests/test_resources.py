from __future__ import annotations

from importlib import resources

from alttp_jp_english_patcher.generate import _save_migration_lines
from alttp_jp_english_patcher.snes_assembly_parser import Assembly
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
