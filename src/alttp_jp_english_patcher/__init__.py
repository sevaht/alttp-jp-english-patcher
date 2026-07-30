"""Generate/deploy the English graft into a pristine jpdasm fork.

The package turns a fork of `spannerisms/jpdasm` (the A Link to the Past JP 1.0
disassembly) into a functional English translation by grafting in the US ROM's
text/menu/graphics subsystems -- emitting the hooked base banks, the graft
banks beside them, a wired ``main.asm``, and the build tooling.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from platformdirs import PlatformDirs

if TYPE_CHECKING:
    from pathlib import Path

APP_NAME = "alttp-jp-english-patcher"
APP_AUTHOR = "sevaht"


@cache
def user_cache_path() -> Path:
    """Where the disassembly source checkouts (usdasm/jpdasm) are cached."""
    path = PlatformDirs(APP_NAME, appauthor=APP_AUTHOR).user_cache_path
    # platformdirs omits appauthor from the path on non-Windows platforms;
    # insert it so all platforms use <author>/<appname>.
    if path.parent.name != APP_AUTHOR:
        path = path.parent / APP_AUTHOR / APP_NAME
    return path
