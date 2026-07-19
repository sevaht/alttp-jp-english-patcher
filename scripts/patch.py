#!/usr/bin/env python3
"""Apply the English graft's edits to the pristine JP base disassembly.

The graft relocates whole subsystems into the expanded ROM (2nd MB) and leaves
small, surgical hooks in the original bank files so the unmodified JP callers
reach our versions. This module is the tool that *writes* those hooks into a
pristine ``../jpdasm`` checkout, so the base edits are generated -- not hand
maintained -- and a fresh fork can reproduce them exactly.

Every edit is located by label or ``#_`` address anchor (never a line number),
so it survives upstream reformatting and fails loud if its target has drifted.
The primitives, all methods of :class:`Patcher`:

* ``rename`` -- free a JP name by prefixing ``UNREACHABLE_`` (the relocated
  copy claims the bare name); the JP body stays byte-identical.
* ``set_operand`` -- rewrite one instruction's operand in place (e.g. point a
  font upload at our ``TheFont``), byte-neutral.
* ``rewrite_reference`` -- retarget one operand symbol (a live ref that must
  reach the preserved JP copy, not the relocated one).
* ``insert_before`` -- splice verbatim lines above a label/anchor (e.g. an
  ``org`` that re-pins data a relocation left behind).
* ``landing_pads`` -- fill a free-ROM (``NULL_``) hole with cross-bank
  forwarding stubs, one per repointed routine, and shrink the pad.
* ``relocate_block`` -- redirect an inline block to a relocated copy with a
  single ``JML``, leaving the rest of the block as the original (now dead)
  instructions so the source still reads like the JP original.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from snes_assembly_parser import Line, Source

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

RULE = ";" + "=" * 99
UNREACHABLE = "UNREACHABLE_"
NULL = "NULL_"

# The forwarding stub a landing pad emits: widen the same-bank JSR return to a
# full 3-byte address on the stack, then jump to the relocated body across the
# bank. Two register flavours (which one is scratch), both 9 bytes.
# (9 bytes each: REP(2) + pull(1) + PHK(1) + push(1) + JML(4).)
_TRAMPOLINE = {
    "A": ["REP #$20", "PLA", "PHK", "PHA", "JML EN_{name}"],
    "X": ["REP #$30", "PLX", "PHK", "PHX", "JML EN_{name}"],
}


@dataclass(frozen=True)
class LandingPad:
    """One forwarding stub: repoint JP ``name`` to ``EN_name`` in another bank.

    ``via`` is the register used as return-widen scratch -- ``"A"`` by default,
    ``"X"`` when the routine takes its argument in A (so A must survive).
    ``comment`` lines are emitted just under the pad's label.
    """

    name: str
    via: str = "A"
    comment: tuple[str, ...] = ()


def _anchor(address: int) -> str:
    return f"#_{address:06X}"


def _lines(texts: Iterable[str]) -> list[Line]:
    return [Line.from_line(text) for text in texts]


@dataclass
class Patcher:
    """A pristine :class:`Source` under edit, addressed by label/anchor."""

    source: Source

    @classmethod
    def from_path(cls, path: Path) -> Patcher:
        return cls(Source.from_path(path))

    # ---- locating -------------------------------------------------------
    def _find(self, locator: str | int) -> int:
        """Index of the line a label name or ``#_``/int address anchor
        names."""
        if isinstance(locator, int):
            anchor = _anchor(locator)
            for index, line in enumerate(self.source.lines):
                if line.label == anchor:
                    return index
            msg = f"no line anchored at ${locator:06X}"
            raise KeyError(msg)
        if locator in self.source.labels:
            return self.source.labels[locator]
        msg = f"no top-level label named {locator!r}"
        raise KeyError(msg)

    # ---- primitives -----------------------------------------------------
    def rename(self, name: str, *, comment: Iterable[str] = ()) -> None:
        """Prefix ``UNREACHABLE_`` onto every definition of ``name``.

        Rewrites the routine label ``name:``, an address-transparent
        ``#name:``, and/or a ``pool name`` directive -- whichever exist -- so
        the bare name frees for the relocated copy to claim while the JP body
        stays put and byte-identical. ``comment`` lines go above the first hit.
        References are left untouched (they resolve to the relocated copy);
        use :meth:`rewrite_reference` for one that must reach the JP body.
        """
        first: int | None = None
        for index, line in enumerate(self.source.lines):
            if line.opcode == "pool" and line.arguments == [name]:
                line.arguments = [UNREACHABLE + name]
            elif line.label == name:
                line.label = UNREACHABLE + name
            elif line.label == f"#{name}":
                line.label = f"#{UNREACHABLE}{name}"
            else:
                continue
            first = index if first is None else first
        if first is None:
            msg = f"rename: no definition of {name!r} found"
            raise KeyError(msg)
        if comment:
            self.source.lines[first:first] = _lines(comment)
        self._touched()

    def set_operand(
        self, anchor: int, instruction: str, *, comment: str | None = None
    ) -> None:
        """Replace the whole instruction on the ``anchor`` line, byte-neutral.

        ``instruction`` is the opcode + operands (no label); the ``#_`` anchor
        and (optional) trailing ``comment`` are re-attached. The caller keeps
        the byte width identical -- this is for operand swaps (a literal, an
        address) that do not move anything downstream.
        """
        index = self._find(anchor)
        text = f"{_anchor(anchor)}: {instruction}"
        if comment:
            text += f" ; {comment}"
        self._replace(index, text)
        self._touched()

    def insert_before(self, locator: str | int, lines: Iterable[str]) -> None:
        """Insert verbatim ``lines`` just above the located label/anchor line
        (e.g. an ``org`` that re-pins data left behind by a relocation)."""
        index = self._find(locator)
        self.source.lines[index:index] = _lines(lines)
        self._touched()

    def rewrite_reference(self, anchor: int, old: str, new: str) -> None:
        """Retarget the symbol ``old`` -> ``new`` in the ``anchor`` line's
        operands (a live reference that must reach the preserved JP copy)."""
        index = self._find(anchor)
        line = self.source.lines[index]
        if old not in line.arguments:
            msg = f"rewrite_reference: ${anchor:06X} has no operand {old!r}"
            raise KeyError(msg)
        line.arguments = [new if arg == old else arg for arg in line.arguments]
        self._touched()

    def landing_pads(
        self,
        free_label: str,
        pads: list[LandingPad],
        *,
        header: Iterable[str] = (),
    ) -> None:
        """Fill the ``NULL_`` free-ROM block ``free_label`` with forwarding
        stubs.

        The pads are laid out from the block's start address; the leftover tail
        stays free as a shrunk ``NULL_`` block (so the following code keeps its
        offset). ``header`` lines are emitted above the first pad.
        """
        start = self._find(free_label)
        end = self._label_boundary(start)
        span = self.source.lines[start:end]
        base = next(
            (ln.address for ln in span if ln.address is not None), None
        )
        if base is None:
            msg = f"landing_pads: {free_label!r} has no address anchor"
            raise KeyError(msg)
        region = sum(line.size for line in span)

        out = _lines(header)
        pc = base
        for pad in pads:
            out.append(Line.from_line(f"{pad.name}:"))
            out += _lines(pad.comment)
            for template in _TRAMPOLINE[pad.via]:
                text = template.format(name=pad.name)
                out.append(Line.from_line(f"{_anchor(pc)}: " + text))
                pc += (
                    2 if text.startswith("REP") else 4 if "JML" in text else 1
                )
        out += _free_block(pc, base + region - pc)
        self.source.lines[start:end] = out
        self._touched()

    def relocate_block(
        self,
        anchor: int,
        jml_target: str,
        *,
        resume: int,
        orphan: list[int] = [],  # noqa: B006
        comment: Iterable[str] = (),
    ) -> None:
        """Redirect an inline block to a relocated copy with a single ``JML``.

        Only the 4-byte ``JML jml_target`` at ``anchor`` is a real change: the
        relocated copy runs the logic and jumps back. Everything from
        ``resume`` onward -- the rest of the displaced block -- is left as the
        original JP instructions (now unreachable, but assembled byte-for-byte,
        so the source still reads like the original and any out-of-bounds read
        still sees the JP ROM). ``resume`` is the address of the first original
        instruction the JML did not land inside; ``orphan`` is the few bytes
        between ``anchor+4`` and ``resume`` -- the tail of the instruction the
        JML's opcode overwrote -- emitted as a lone ``db`` (usually one byte,
        or none if the JML happens to land on a boundary).
        """
        start = self._find(anchor)
        jml_end = anchor + 4
        if resume < jml_end or len(orphan) != resume - jml_end:
            need = resume - jml_end
            msg = (
                f"relocate_block: resume ${resume:06X} needs {need} orphan "
                f"byte(s) after the JML, got {len(orphan)}"
            )
            raise ValueError(msg)
        stop = next(
            index
            for index in range(start + 1, len(self.source.lines))
            if (addr := self.source.lines[index].address) is not None
            and addr >= resume
        )
        out = _lines(comment)
        out.append(Line.from_line(f"{_anchor(anchor)}: JML {jml_target}"))
        if orphan:
            out += _byte_rows(jml_end, orphan)
        self.source.lines[start:stop] = out
        self._touched()

    def _label_boundary(self, start: int) -> int:
        """Index one past the block at ``start``: the next top-level label or
        pool (where a ``NULL_``/routine block ends)."""
        bounds = sorted(
            {
                *self.source.labels.values(),
                *(s for s, _ in self.source.pools.values()),
            }
        )
        return next((b for b in bounds if b > start), len(self.source.lines))

    # ---- output ---------------------------------------------------------
    def _replace(self, index: int, text: str) -> None:
        self.source.lines[index] = Line.from_line(text)

    def _touched(self) -> None:
        """Re-derive label/pool/size indexes after a line mutation."""
        self.source.reindex()

    def render(self) -> str:
        return "\n".join(str(line) for line in self.source.lines) + "\n"

    def save(self, path: Path) -> None:
        path.write_text(self.render())


def _free_block(address: int, size: int) -> list[Line]:
    """A ``NULL_`` free-ROM marker of ``size`` ``$FF`` bytes (8 per row)."""
    head = [
        Line.from_line(RULE),
        Line.from_line(f"; FREE ROM: 0x{size:X}"),
        Line.from_line(RULE),
        Line.from_line(f"{NULL}{address:06X}:"),
    ]
    return head + _byte_rows(address, [0xFF] * size)


def _byte_rows(
    address: int, values: list[int], per_row: int = 8
) -> list[Line]:
    """``db`` rows for ``values`` (``per_row`` each), anchored from
    ``address``."""
    rows: list[Line] = []
    for offset in range(0, len(values), per_row):
        chunk = values[offset : offset + per_row]
        body = ", ".join(f"${value:02X}" for value in chunk)
        rows.append(Line.from_line(f"{_anchor(address + offset)}: db {body}"))
    return rows


__all__ = ["LandingPad", "Patcher"]
