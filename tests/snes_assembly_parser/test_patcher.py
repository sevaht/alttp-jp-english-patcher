"""Tests for snes_assembly_parser.patcher.Patcher."""

from __future__ import annotations

from alttp_jp_english_patcher.snes_assembly_parser import (
    Assembly,
    LandingPad,
    Patcher,
)


def test_landing_pads_preserve_following_block_header_comment() -> None:
    # A NULL_ free region followed by the *next* block's header comment: re-
    # using the region for landing-pad stubs must not swallow that comment.
    src = [
        "org $018000",
        "NULL_018000:",
        "#_018000: db $FF, $FF, $FF, $FF, $FF, $FF, $FF, $FF",
        "#_018008: db $FF, $FF, $FF, $FF, $FF, $FF, $FF, $FF",
        "",
        "; header for NextThing",
        "NextThing:",
        "#_018010: db $01",
    ]
    patcher = Patcher(Assembly.from_content(src))
    patcher.landing_pads("NULL_018000", [LandingPad("Foo", "EN_Foo")])

    lines = patcher.render().splitlines()
    assert any("JSL EN_Foo" in line for line in lines)  # the pad was placed

    header = lines.index("; header for NextThing")
    following = next(
        i for i, line in enumerate(lines) if line.startswith("NextThing")
    )
    # the header comment survived, still directly above its block ...
    assert header < following
    # ... and sits after the shrunk free fill, not before the stubs
    assert any("db $FF" in line for line in lines[:header])
    assert any("JSL EN_Foo" in line for line in lines[:header])
