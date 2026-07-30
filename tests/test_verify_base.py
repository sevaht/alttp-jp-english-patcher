from __future__ import annotations

import os
from pathlib import Path

import pytest

from alttp_jp_english_patcher import user_cache_path, verify_base


def _source(label: str, env_var: str, sentinel: str) -> Path | None:
    """An existing disassembly checkout for ``label``, or ``None``.

    Looks at ``$env_var`` first, then the CLI's platformdirs cache; only an
    already-present checkout (verified by ``sentinel``) counts -- the test
    never clones.
    """
    env = os.environ.get(env_var)
    candidate = Path(env) if env else user_cache_path() / label
    return candidate if (candidate / sentinel).is_file() else None


@pytest.mark.slow
def test_generated_base_banks_match_frozen_hashes() -> None:
    """The generated base-bank hooks still reproduce ``reference_hashes.txt``.

    This is the drift guard: it runs a full build against the pristine
    disassemblies and compares each hooked base bank's signature. It is slow
    (~15s) so it is **opt-in** -- marked ``slow`` and deselected by default;
    run it with ``pytest -m slow``. It also needs both checkouts (the CLI's
    cached ``usdasm``/``jpdasm``, or ``USDASM_DIR``/``JPDASM_DIR``) and skips
    when they are absent.
    """
    usdasm = _source("usdasm", "USDASM_DIR", "bank_0E.asm")
    jpdasm = _source("jpdasm", "JPDASM_DIR", "bank_00.asm")
    if usdasm is None or jpdasm is None:
        pytest.skip(
            "usdasm/jpdasm checkouts not available (run the patcher once, or "
            "set USDASM_DIR / JPDASM_DIR)"
        )

    got = verify_base.compute(jpdasm, usdasm)
    reference = verify_base.load_reference()
    mismatched = sorted(b for b in got if got[b] != reference.get(b))
    assert not mismatched, (
        f"base-bank signature drift in {mismatched}. If intentional, re-freeze"
        " with: python -m alttp_jp_english_patcher.verify_base"
        " --src JPDASM --usdasm USDASM --freeze"
    )
