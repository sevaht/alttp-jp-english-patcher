#!/usr/bin/env python3
"""Graft toolkit: relocate US disassembly code into the expanded English ROM.

The parsing/relocation primitives (the ``Assembly`` unit -- sized extraction,
``instructions``/``data``/``notes``, PC-tracked ``render``) come from the
**snes-assembly-parser** library. This module keeps only the parts specific to
the English graft, the one a generator reaches for being:

* :class:`Relocation` -- accumulate the relocated ``Assembly`` pieces at their
  target ``org``s and emit ``EN_``-namespaced :class:`Placement`\\ s. A
  generator just ``place``s each piece and calls
  :meth:`~Relocation.placements`;
  the collect-names, namespace, and hook-alias mechanics are all buried here
  (:func:`collect_names`, :func:`en_namespace`, :func:`sublabel_names`,
  :class:`Placement`). The pieces are grouped into ``bank_XX.asm`` files by
  :meth:`snes_assembly_parser.Rom.write` (see :func:`bank_header`).
* :func:`mirror`     -- the "+$20 mirror" US->English address relocation.
* :func:`substitute` -- an assertive multi-line text edit (for comment/caption
  rewrites a single-``Line`` edit can't express).

The library is vendored into this package as ``.snes_assembly_parser`` (its
standalone CLI is not vendored, only the importable API).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .snes_assembly_parser import Assembly

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


def require_start(body: Assembly) -> int:
    """A relocated body's first anchor address (raises if it has none)."""
    start = body.start_address
    if start is None:
        msg = "relocated body has no address anchor"
        raise ValueError(msg)
    return start


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
    aliased: frozenset[str] = frozenset(),
    shared: frozenset[str] = frozenset(),
) -> str:
    """Rename the relocated symbols in ``text`` into the ``EN_`` namespace.

    * ``names`` is the *global* set of relocated symbols (from
      :func:`collect_names` over every block); each occurrence is prefixed
      ``EN_`` so it can never collide with the identically-named (now dead) JP
      original, and cross-block references stay in step with their definitions.
    * ``shared`` names are left bare -- globals referenced from outside this
      subsystem (e.g. ``TheFont``, read by bank_00's font upload).
    * Each name in ``aliased`` additionally keeps its bare form as an alias
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

    for hook in sorted(aliased):
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


def bank_header(bank: int) -> str:
    """The header comment atop a generated ``bank_XX.asm`` graft file.

    Passed to :meth:`snes_assembly_parser.Rom.write`, which groups the
    relocation pieces by ROM bank (``org >> 16``) and writes each
    ``bank_XX.asm`` beside the base ``bank_00`` .. ``bank_1F`` -- following the
    disassembly's one-file-per-bank convention (asar resolves the cross-bank
    ``EN_`` references across all the includes, so the split is byte-neutral).
    """
    return (
        f"; bank_{bank:02X}.asm -- English graft relocated into the "
        f"expanded ROM (bank ${bank:02X}).\n"
        "; generated by english/generate.sh; do not hand-edit."
    )


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

    This buries the render -> collect-names -> namespace tail every generator
    used to repeat: a generator just :meth:`place`\\ s each extracted (and
    edited) :class:`~snes_assembly_parser.Assembly` piece at its address and
    calls :meth:`placements`. Symbols are namespaced *globally* across all
    pieces at once, so a reference in one piece to a definition in another
    stays in step; ``hooks`` and ``shared`` are applied uniformly (a hook alias
    only materialises in the piece that defines it, so this is safe).

    A relocation is also the single source of truth for what it *hooks*. A
    generator lists the JP entry points it intercepts in :attr:`hooked` and the
    blocks it carries along in :attr:`carried`; the driver frees every hooked
    name in the base and then, *per name*, either lets the relocated copy claim
    a bare alias (recorded in :attr:`aliased`) or -- when a same-bank caller
    stays behind and cannot reach the copy -- lays a landing-pad stub in
    :attr:`pad_region`. Which of the two a hook needs is computed from the
    program's callers (:meth:`snes_assembly_parser.Rom.needs_landing_pad`), not
    declared, so a hooked function is described once, here.
    """

    #: The JP entry points this relocation intercepts, in the order a landing
    #: pad would lay them (freed in the base; each becomes an alias or a pad).
    hooked: tuple[str, ...] = ()
    #: The source blocks this relocation carries out of the base with it. A
    #: hooked name's same-bank caller only forces a pad if its block is *not*
    #: in here (it stays behind); a caller that moves along reaches the copy.
    carried: frozenset[str] = field(default_factory=frozenset)
    #: Free-ROM (``NULL_``) label to lay landing-pad stubs in, and their header
    #: comment -- for the hooks a caller-analysis decides need one.
    pad_region: str | None = None
    pad_header: tuple[str, ...] = ()
    #: Optional comment lines to annotate a freed base definition with (why the
    #: JP name is dead / where its data went), keyed by hook name.
    hook_notes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: The subset of :attr:`hooked` that claim a bare alias in the relocated
    #: code (the ones *not* given a pad). Derived by the driver's hook wiring,
    #: not declared.
    aliased: frozenset[str] = field(default_factory=frozenset)
    shared: frozenset[str] = field(default_factory=frozenset)
    #: When ``False`` (the change-free baseline), no :attr:`aliased` alias is
    #: emitted -- the relocated names stay purely ``EN_``, so no unmodified
    #: caller is redirected.
    changes: bool = True
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

    def place_mirror(
        self, body: Assembly, note: str = "", *, shift: int = 0
    ) -> Relocation:
        """:meth:`place` ``body`` at the +$20 mirror of its own first anchor.

        The common case: a routine pulled from the US/JP bank keeps its layout,
        so its English copy just lands $200000 higher. ``shift`` nudges the org
        when an earlier edit grew the region the body follows.
        """
        return self.place(body, mirror(require_start(body)) + shift, note)

    def placements(self) -> list[Placement]:
        """The namespaced :class:`Placement`\\ s (org + body + note) this
        relocation emits, before joining into any file.

        The ``EN_`` prefix is applied to every relocated symbol (except
        :attr:`shared`); each :attr:`hooks` name additionally keeps its bare
        form as an alias so unmodified callers resolve. Returning the pieces
        (rather than a joined file) lets a caller regroup them -- e.g. by ROM
        bank via :meth:`snes_assembly_parser.Rom.write`.
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
        aliased = self.aliased if self.changes else frozenset()
        return [
            Placement(
                org,
                (
                    en_namespace(
                        text, names, aliased=aliased, shared=self.shared
                    )
                    if should_namespace
                    else text
                ),
                note,
            )
            for org, text, note, should_namespace in rendered
        ]
