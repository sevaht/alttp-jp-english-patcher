#!/usr/bin/env python3
"""Graft toolkit: relocate US disassembly code into the expanded English ROM.

The parsing/relocation primitives (the ``Assembly`` unit -- sized extraction,
``instructions``/``data``/``notes``, PC-tracked ``render``) come from the
**snes-assembly-parser** library. This module keeps only the parts specific to
the English graft, the one a generator reaches for being:

* :class:`Relocation` -- accumulate the relocated ``Assembly`` pieces at their
  target ``org``s and emit one ``EN_``-namespaced source file. A generator just
  ``place``s each piece and calls ``render``; the collect-names, namespace,
  hook-alias, and assemble mechanics are all buried here
  (:func:`collect_names`, :func:`en_namespace`, :func:`sublabel_names`,
  :class:`Placement`, :func:`assemble`).
* :func:`mirror`     -- the "+$20 mirror" US->English address relocation.
* :func:`substitute` -- an assertive multi-line text edit (for comment/caption
  rewrites a single-``Line`` edit can't express).

The library is imported as a plain package (``snes_assembly_parser``); its
``application``/``__main__`` modules -- the only ones with a third-party
dependency -- are never touched, so a bare checkout on ``PYTHONPATH`` is enough
(see ``generate.sh``).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from snes_assembly_parser import Assembly

#: US -> English address offset (+$20 banks, i.e. +2 MB / 0x200000).
MIRROR = 0x200000

_LABEL_DEF = re.compile(r"^#?([A-Za-z]\w*):")  # 'Foo:' / '#Foo:' (letter-led)
_POOL_DEF = re.compile(r"^pool[ \t]+([A-Za-z_]\w*)")  # 'pool Foo'
# Address-in-the-name markers: NULL_ (free ROM), UNREACHABLE_ (dead code).
# These are position markers, not relocatable symbols, so never namespace/keep
# them.
_ADDR_MARKER = re.compile(r"^(NULL|UNREACHABLE)_[0-9A-Fa-f]+$")


def mirror(us_addr: int) -> int:
    """Return the +$20 mirror of a US ROM address (bank ``$0N`` -> ``$2N``)."""
    return us_addr + MIRROR


def substitute(text: str, old: str, new: str, count: int = 1) -> str:
    """Assertive text replace for multi-line comment/caption rewrites.

    ``old`` must occur exactly ``count`` times, so a drifting upstream can
    never silently no-op the edit. Used where the replacement spans multiple
    lines and so cannot go through a single-``Line`` :meth:`Assembly.replace`.
    """
    found = text.count(old)
    if found != count:
        msg = f"substitute {old!r}: expected {count}, found {found}"
        raise AssertionError(msg)
    return text.replace(old, new)


def collect_names(text: str) -> set[str]:
    """Every top-level label and ``pool`` base defined in ``text``.

    Callers union this across all relocated blocks so that a reference in one
    block (e.g. the engine reading ``Message_Data``) is renamed consistently
    with its definition in another block.
    """
    names: set[str] = set()
    for line in text.split("\n"):
        label = _LABEL_DEF.match(line)
        if label and not _ADDR_MARKER.match(label.group(1)):
            names.add(label.group(1))
        pool = _POOL_DEF.match(line)
        if pool and pool.group(1) != "off":
            names.add(pool.group(1))
    return names


def en_namespace(
    text: str,
    names: set[str],
    hooks: frozenset[str] = frozenset(),
    shared: frozenset[str] = frozenset(),
) -> str:
    """Rename the relocated symbols in ``text`` into the ``EN_`` namespace.

    * ``names`` is the *global* set of relocated symbols (from
      :func:`collect_names` over every block); each occurrence is prefixed
      ``EN_`` so it can never collide with the identically-named (now dead) JP
      original, and cross-block references stay in step with their definitions.
    * ``shared`` names are left bare -- globals referenced from outside this
      subsystem (e.g. ``TheFont``, read by bank_00's font upload).
    * Each name in ``hooks`` additionally keeps its bare form as an alias
      placed directly above the ``EN_`` definition, so an unmodified JP
      ``JSL Foo`` still lands on our version while our own code calls
      ``EN_Foo``.
    * Comments (everything after ``;``) and dot-sublabels (``.loop``) are
      untouched.
    """
    names = set(names) - set(shared)
    if not names:
        return text

    # Longest-first so 'Foo_bar' is matched before 'Foo'; the trailing (?![\w])
    # then prevents clipping 'Foo' out of 'Foo_bar'. The leading (?<![\w.])
    # skips mid-identifier hits and dot-sublabel references (.Foo).
    alternation = "|".join(
        re.escape(name) for name in sorted(names, key=len, reverse=True)
    )
    token = re.compile(rf"(?<![\w.])(?:{alternation})(?![\w])")

    namespaced_lines = []
    for line in text.split("\n"):
        body, separator, comment = line.partition(";")
        prefixed = token.sub(lambda match: "EN_" + match.group(0), body)
        namespaced_lines.append(prefixed + separator + comment)
    text = "\n".join(namespaced_lines)

    for hook in sorted(hooks):
        text = re.sub(
            rf"^(#?)EN_{re.escape(hook)}:",
            rf"\1{hook}:\n\1EN_{hook}:",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    return text


@dataclass
class Placement:
    """A pinned chunk of output: an ``org`` plus its body, with a leading
    note."""

    org: int
    body: str
    note: str = ""

    def render(self) -> str:
        head = f"; {self.note}\n" if self.note else ""
        return f"{head}org ${self.org:06X}\n{self.body.rstrip()}\n"


def assemble(header: str, blocks: list[Placement]) -> str:
    """Join a header comment and rendered blocks into the final source file."""
    body = "\n\n".join(block.render() for block in blocks)
    return header.rstrip("\n") + "\n\n" + body + "\n"


def write_banks(placements: list[Placement], out_dir: Path) -> list[str]:
    """Group ``placements`` by ROM bank (``org >> 16``) and write each bank to
    ``out_dir`` as ``bank_XX.asm``, its ``org`` blocks in ascending address
    order.

    This follows the disassembly's one-file-per-bank convention, so the graft
    slots in beside the base ``bank_00.asm`` .. ``bank_1F.asm`` files (asar
    resolves the cross-bank ``EN_`` references across all the includes, so the
    split is byte-neutral). Returns the bank file names written, in bank order.
    """
    by_bank: dict[int, list[Placement]] = defaultdict(list)
    for placement in placements:
        by_bank[placement.org >> 16].append(placement)
    written: list[str] = []
    for bank in sorted(by_bank):
        blocks = sorted(by_bank[bank], key=lambda placement: placement.org)
        header = (
            f"; bank_{bank:02X}.asm -- English graft relocated into the "
            f"expanded ROM (bank ${bank:02X}).\n"
            "; generated by english/generate.sh; do not hand-edit."
        )
        name = f"bank_{bank:02X}.asm"
        (out_dir / name).write_text(assemble(header, blocks))
        written.append(name)
    return written


def sublabel_names(text: str, base_names: set[str]) -> set[str]:
    """Expand ``base_names`` with the ``Base_sub`` pool-sublabel reference
    tokens that appear in ``text``.

    An asar ``pool Foo`` exposes its ``.bar`` sublabel at the reference site as
    ``Foo_bar``; :func:`collect_names` records only the pool base ``Foo``, and
    the plain word-boundary rename would skip the ``Foo_bar`` form, so add each
    such token so it namespaces in step with its pool.
    """
    names = set(base_names)
    for base in base_names:
        names |= set(re.findall(rf"\b{re.escape(base)}_\w+", text))
    return names


@dataclass
class Relocation:
    """Accumulate relocated code pieces at their target ``org``s, then emit one
    ``EN_``-namespaced source file.

    This buries the render -> collect-names -> namespace -> assemble tail every
    generator used to repeat: a generator just :meth:`place`\\ s each extracted
    (and edited) :class:`~snes_assembly_parser.Assembly` piece at its address
    and calls :meth:`render`. Symbols are namespaced *globally* across all
    pieces at once, so a reference in one piece to a definition in another
    stays in step; ``hooks`` and ``shared`` are applied uniformly (a hook alias
    only materialises in the piece that defines it, so this is safe).
    """

    header: str
    hooks: frozenset[str] = field(default_factory=frozenset)
    shared: frozenset[str] = field(default_factory=frozenset)
    _pieces: list[tuple[int, Assembly | str, str, bool]] = field(
        default_factory=list
    )

    def place(
        self,
        body: Assembly | str,
        org: int,
        note: str = "",
        *,
        namespace: bool = True,
    ) -> Relocation:
        """Pin ``body`` at absolute ``org`` (with an optional block note).

        ``body`` is usually an :class:`~snes_assembly_parser.Assembly`
        (rendered at ``org``); a plain ``str`` is taken as an already-rendered
        body. With ``namespace=False`` the piece is emitted verbatim and its
        symbols are left out of the shared name set -- for a raw font blob or a
        hand-written stub already in its final (``EN_``/hook-aliased) form.
        """
        self._pieces.append((org, body, note, namespace))
        return self

    def placements(self) -> list[Placement]:
        """The namespaced :class:`Placement`\\ s (org + body + note) this
        relocation emits, before joining into any file.

        The ``EN_`` prefix is applied to every relocated symbol (except
        :attr:`shared`); each :attr:`hooks` name additionally keeps its bare
        form as an alias so unmodified callers resolve. Returning the pieces
        (rather than a joined file) lets a caller regroup them -- e.g. by ROM
        bank via :func:`write_banks`.
        """
        rendered = [
            (
                org,
                body if isinstance(body, str) else body.render(org),
                note,
                should_namespace,
            )
            for org, body, note, should_namespace in self._pieces
        ]
        # Only namespaced pieces contribute to (and receive) the shared rename;
        # verbatim pieces already carry their final symbols.
        combined = "\n".join(
            text
            for _, text, _, should_namespace in rendered
            if should_namespace
        )
        names = sublabel_names(combined, collect_names(combined))
        return [
            Placement(
                org,
                (
                    en_namespace(
                        text, names, hooks=self.hooks, shared=self.shared
                    )
                    if should_namespace
                    else text
                ),
                note,
            )
            for org, text, note, should_namespace in rendered
        ]

    def render(self) -> str:
        """Namespace every piece and assemble them into one source file."""
        return assemble(self.header, self.placements())
