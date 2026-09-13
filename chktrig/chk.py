"""
Parser for the `scenario.chk` chunk format - resync-capable.

The file is *supposed* to be a flat sequence of tagged, length-prefixed
sections:

    4 bytes  ASCII tag (e.g. b'TRIG', b'STR ' - note the trailing space)
    4 bytes  little-endian u32 length of this section's data
    N bytes  section data

...with no top-level container: just tag/length/data until the bytes run
out. In practice, real custom maps routinely have this broken on purpose.
Popular RPG-style maps are a favorite target for "protection" tools whose
whole point is stopping exactly this kind of parsing, and the length-lying
technique long predates any particular protector: forum lore from the
2000s-era StarForge/PROEdit/GUEdit protectors already describes corrupting
section lengths and injecting fake sections (see staredit.net topic 984 and
the "Unprotecting Starcraft Map" community notes). We hit this firsthand on
a real, current map: both `MTXM`'s and `TRIG`'s declared lengths were wrong
(one short, one long enough to run past EOF), while every section around
them was untouched and perfectly framed.

So this parser doesn't just trust each declared length. After reading a
header, it checks whether `offset + 8 + length` actually lands on another
recognizable tag (or exactly at EOF). If it doesn't, that length is treated
as corrupt: we scan forward for the nearest position that looks like a real
section header - preferring one whose tag has a document-verified fixed
size (see FIXED_SIZES below) when there's a choice - and treat everything
between as the current section's *real* data. If nothing is found before
EOF, the rest of the file becomes this section's data (this is what happens
to TRIG itself when its declared length overshoots the file: the remainder
is still decoded, just clamped to whatever whole number of 2400-byte
trigger records actually fits - see triggers.decode_trig).

A tag can also legally appear more than once (again, most famously exploited
by protectors); like the reference implementations (e.g. PyMS), we keep the
*last* occurrence of each tag as authoritative, matching game/editor
behavior.

Source: staredit.net / SEN wiki's Scenario.chk page and CHK format notes,
cross-checked against PyMS's CHK.py (github.com/poiuyqwert/PyMS) for the
tag vocabulary, plus the resync behavior verified empirically against a
real protected map (see docs/chk_trigger_format.md).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# every section tag PyMS's CHK.SECTION_TYPES recognizes (github.com/poiuyqwert/PyMS)
KNOWN_TAGS: frozenset[bytes] = frozenset(
    t.encode("ascii")
    for t in (
        "TYPE", "VER ", "IVER", "IVE2", "VCOD", "IOWN", "OWNR", "ERA ", "DIM ",
        "SIDE", "MTXM", "PUNI", "UPGR", "PTEC", "UNIT", "ISOM", "TILE", "DD2 ",
        "THG2", "MASK", "STR ", "STRx", "UPRP", "UPUS", "MRGN", "TRIG", "MBRF",
        "SPRP", "FORC", "WAV ", "UNIS", "UPGS", "TECS", "SWNM", "COLR", "CRGB",
        "PUPx", "PTEx", "UNIx", "UPGx", "TECx",
    )
)

# sections whose size the game itself hard-requires (per starcraftai.com's CHK
# Format notes and the SEN wiki), used to prefer the right candidate when
# resyncing past a corrupted length rather than just taking the nearest match.
FIXED_SIZES: dict[bytes, frozenset[int]] = {
    b"PUNI": frozenset({5700}),
    b"UPGR": frozenset({1748}),
    b"PTEC": frozenset({912}),
    b"MRGN": frozenset({5100, 1280}),  # 255 locations (1.04+) or 64 (pre-1.04)
}


@dataclass
class CHKFile:
    # tag -> bytes, last occurrence wins (matches game/editor behavior)
    sections: dict[bytes, bytes] = field(default_factory=dict)
    # every tag occurrence in file order, duplicates included
    section_order: list[bytes] = field(default_factory=list)
    # tags whose declared length had to be corrected via resync, in order found
    resynced: list[bytes] = field(default_factory=list)

    def get(self, tag: str | bytes) -> bytes | None:
        if isinstance(tag, str):
            tag = tag.encode("ascii")
        return self.sections.get(tag)

    def __contains__(self, tag: str | bytes) -> bool:
        if isinstance(tag, str):
            tag = tag.encode("ascii")
        return tag in self.sections


def _looks_like_header(data: bytes, pos: int, n: int) -> bool:
    if pos == n:
        return True  # ending exactly at EOF is a perfectly valid boundary
    if pos + 8 > n:
        return False
    tag = data[pos : pos + 4]
    if tag not in KNOWN_TAGS:
        return False
    allowed = FIXED_SIZES.get(tag)
    if allowed is not None:
        (length,) = struct.unpack_from("<I", data, pos + 4)
        return length in allowed
    return True


def _find_next_header(data: bytes, start: int, n: int) -> int | None:
    """Scan forward for the nearest position that looks like a real section
    header. Prefers (by trying in two passes) a tag with a verified fixed
    size, since those can't be coincidental matches; falls back to any
    recognized tag if no fixed-size candidate turns up first."""
    fallback = None
    for cand in range(start, n - 8 + 1):
        tag = data[cand : cand + 4]
        if tag not in KNOWN_TAGS:
            continue
        allowed = FIXED_SIZES.get(tag)
        if allowed is not None:
            (length,) = struct.unpack_from("<I", data, cand + 4)
            if length in allowed:
                return cand  # high-confidence match, stop immediately
            continue  # tag matched but size didn't - not this one
        if fallback is None:
            fallback = cand
    return fallback


def parse(data: bytes) -> CHKFile:
    chk = CHKFile()
    offset = 0
    n = len(data)
    while offset + 8 <= n:
        tag, length = struct.unpack_from("<4sI", data, offset)
        data_start = offset + 8
        naive_end = data_start + length

        if naive_end <= n and _looks_like_header(data, naive_end, n):
            end = naive_end
        else:
            found = _find_next_header(data, data_start, n)
            end = found if found is not None else n
            chk.resynced.append(tag)

        chk.sections[tag] = data[data_start:end]
        chk.section_order.append(tag)
        offset = end
    return chk
