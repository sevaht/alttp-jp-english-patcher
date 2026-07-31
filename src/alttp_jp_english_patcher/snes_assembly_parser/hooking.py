"""Function-interception (hooking) primitives shared by :class:`Assembly` and
:class:`Rom`.

Hooking means freeing an original routine's name so a relocated copy can claim
it, and -- when same-bank ``JSR`` callers cannot reach the copy across banks --
filling a free-ROM hole with a small forwarding stub (a *landing pad*)
under the
freed name. This module holds the value types and pure line-builders for that;
the addressing and mutation live on :class:`Assembly`/:class:`Rom`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .source import Line

#: Prefix that frees a routine's name (the disassembly's "dead code" marker).
UNREACHABLE_PREFIX = "UNREACHABLE_"
#: Prefix marking a free-ROM hole.
NULL_PREFIX = "NULL_"
#: A full-width separator rule between blocks.
RULE = ";" + "=" * 99

# The forwarding stub a landing pad emits: a register-transparent JSL/RTS
# bridge. A same-bank ``JSR name`` lands here; the ``JSL`` calls the relocated
# body across the bank (pushing a 3-byte return to this pad), the body returns
# with ``RTL`` to the ``RTS``, which pops the JSR's 2-byte return to its
# caller.
# No register is touched, so a caller's argument in A/X/Y passes straight
# through. 5 bytes (JSL 4 + RTS 1).
_STUB_OPCODE_SIZES = {"JSL": 4, "RTS": 1}


def anchor_label(address: int) -> str:
    """The ``#_<hex>`` address-anchor label for ``address``."""
    return f"#_{address:06X}"


@dataclass(frozen=True)
class LandingPad:
    """A forwarding stub: repoint the freed name ``name`` to ``target``.

    The relocated body ``target`` (in another bank) must end in ``RTL``.
    ``comment`` lines are emitted just under the pad's label.
    """

    name: str
    target: str
    comment: tuple[str, ...] = field(default=())


def landing_pad_lines(
    pads: list[LandingPad], base_address: int
) -> tuple[list[Line], int]:
    """Build the stub lines for ``pads`` laid out from ``base_address``.

    Returns the lines and the program counter just past the last stub, so the
    caller can back-fill the remaining free-ROM tail.
    """
    lines: list[Line] = []
    program_counter = base_address
    for pad in pads:
        lines.append(Line.from_line(f"{pad.name}:"))
        lines.extend(Line.from_line(text) for text in pad.comment)
        for opcode, operand in (("JSL", pad.target), ("RTS", "")):
            text = f"{opcode} {operand}".rstrip()
            lines.append(
                Line.from_line(f"{anchor_label(program_counter)}: {text}")
            )
            program_counter += _STUB_OPCODE_SIZES[opcode]
    return lines, program_counter


def byte_rows(address: int, values: list[int], per_row: int = 8) -> list[Line]:
    """``db`` rows for ``values`` (``per_row`` per line), anchored from
    ``address``."""
    rows: list[Line] = []
    for offset in range(0, len(values), per_row):
        chunk = values[offset : offset + per_row]
        body = ", ".join(f"${value:02X}" for value in chunk)
        line = Line.from_line(f"{anchor_label(address + offset)}: db {body}")
        # A ``db`` row's size is just its byte count; set it so the row is
        # correct even when rendered straight into a placed Assembly (where
        # render reads .size rather than recomputing it via a later resize).
        line.size = len(chunk)
        rows.append(line)
    return rows


def _free_header(address: int, size: int) -> list[Line]:
    return [
        Line.from_line(RULE),
        Line.from_line(f"; FREE ROM: 0x{size:X}"),
        Line.from_line(RULE),
        Line.from_line(f"{NULL_PREFIX}{address:06X}:"),
    ]


def free_block(address: int, size: int) -> list[Line]:
    """A ``NULL_`` free-ROM marker of ``size`` ``$FF`` bytes, spelled out as
    explicit ``db`` rows."""
    return _free_header(address, size) + byte_rows(address, [0xFF] * size)


def free_block_padded(address: int, size: int) -> list[Line]:
    """A ``NULL_`` free-ROM marker of ``size`` ``$FF`` bytes, filled by a
    single ``padbyte``/``pad`` jump instead of a wall of ``db`` rows -- for a
    span too large to usefully spell out byte-by-byte.

    ``pad`` targets ``address + size - 1`` (not the gap's true end): asar's
    LoROM address math only maps ``$xx8000-$xxFFFF`` per bank, so a target
    landing exactly on the *next* bank (low bits ``$0000``, e.g. padding a
    bank's tail up to ``$210000``) resolves to invalid ROM space and ``pad``
    silently no-ops (found empirically: it fills correctly one byte short of
    a bank boundary, not at all exactly on one). The last byte is written
    explicitly instead, sidestepping the boundary regardless of whether this
    particular gap happens to end on one.
    """
    last = address + size - 1
    # padbyte/pad don't emit at a byte-for-byte-attributable address (like
    # `org`, a directive rather than data), so only the fill's start and its
    # explicit trailing byte carry `#_` anchors -- matching the convention's
    # "byte-emitting lines are anchored" rule, not "every line". Sizes are set
    # explicitly (size - 1 / 0 / 1) so PC tracking is correct even when this
    # is rendered straight into a placed Assembly (as file_select() does),
    # not just joined as already-final text (as Rom.write() does) -- same
    # reason byte_rows() sets its own .size below.
    padbyte_line = Line.from_line(f"{anchor_label(address)}: padbyte $FF")
    padbyte_line.size = size - 1
    trailing_byte = Line.from_line(f"{anchor_label(last)}: db $FF")
    trailing_byte.size = 1
    return [
        *_free_header(address, size),
        padbyte_line,
        Line.from_line(f"pad ${last:06X}"),
        trailing_byte,
    ]


def free_space(
    address: int, size: int, *, padbyte_threshold: int
) -> list[Line]:
    """A ``NULL_`` free-ROM span: :func:`free_block` normally, or
    :func:`free_block_padded` once ``size`` exceeds ``padbyte_threshold``.

    ``padbyte_threshold <= 0`` disables padbyte entirely (always explicit
    rows, matching the base disassembly's own convention of writing every
    byte); ``size <= 0`` emits nothing (no gap to fill).
    """
    if size <= 0:
        return []
    if padbyte_threshold > 0 and size > padbyte_threshold:
        return free_block_padded(address, size)
    return free_block(address, size)
