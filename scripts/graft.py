#!/usr/bin/env python3
"""Graft toolkit: relocate US disassembly code into the expanded English ROM.

The parsing/relocation primitives (``Source``, sized ``Segment`` extraction,
``code``/``data``/``note``, PC-tracked ``render``) now come from the
**snes-assembly-parser** library -- this module keeps only the parts specific
to the English graft:

* :func:`mirror`       -- the "+$20 mirror" US->English address relocation.
* :func:`substitute`   -- an assertive multi-line text edit (for
  comment/caption rewrites a single-``Line`` edit can't express).
* :func:`collect_names` / :func:`en_namespace` -- rename every relocated
  symbol into the ``EN_`` namespace so it can never collide with the untouched
  JP original, while giving each *hook* both its bare name (so unmodified JP
  callers still resolve) and its ``EN_`` name.
* :class:`Placement` / :func:`assemble` -- pin rendered blocks to their ``org``
  and join them into the final source file.

The library is imported as a plain package (``snes_assembly_parser.source`` /
``.segment``); its ``application``/``__main__`` modules -- the only ones with a
third-party dependency -- are never touched, so a bare checkout on
``PYTHONPATH`` is enough (see ``generate_us_text.sh``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    lines and so cannot go through a single-``Line`` :meth:`Segment.replace`.
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
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    token = re.compile(rf"(?<![\w.])(?:{alt})(?![\w])")

    out = []
    for line in text.split("\n"):
        body, sep, comment = line.partition(";")
        out.append(
            token.sub(lambda m: "EN_" + m.group(0), body) + sep + comment
        )
    text = "\n".join(out)

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
