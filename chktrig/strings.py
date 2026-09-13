"""
Decode the STR / STRx string table sections.

STR  (classic): u16 count, then `count` x u16 offsets (relative to the start
of the section), then null-terminated strings packed after the offset table.
Max ~64KB section, hence STRx for Remastered maps that need more strings:
same shape but u32 count/offsets.

String id 0 is conventionally "no string" (empty/unused) - callers should
treat lookups of 0 accordingly rather than as a real string.

Source: PyMS's CHKSectionSTR.py (github.com/poiuyqwert/PyMS), cross-checked
against the SEN wiki's Scenario.chk page.

## Corrupted offsets (protection)

On a real protected map (see docs/chk_trigger_format.md), we found roughly
38% of this table's declared offsets don't point at a real string boundary
at all - they land a handful of bytes *into* the correct string instead of
at its start (e.g. declared offset resolves to `"con"` where the real
string is `"Spirit Beacon"` - 10 bytes short of where it should point).
Tellingly, corruption was concentrated almost entirely on the string ids
that MRGN locations reference by name (60 of 64 in the map we checked) -
this reads as a targeted attempt to hide location names specifically,
since those tend to reveal map design. The actual string *data* is left
completely intact; only the offset table lies.

Recovery is simple and empirically confirmed: since the corruption always
seems to overshoot forward into a valid string rather than scramble things
outright, snapping an invalid offset backward to the nearest position that
*does* sit right after a real `\\x00` (or at the very start of the string
blob) recovers the correct text. `decode_str`/`decode_strx` do this for
every offset, not just ones known to belong to a protected map - a
correctly authored table is unaffected (every offset already sits on a
boundary, so snapping is a no-op), and legitimate string reuse/dedup
(multiple ids sharing one physical string) is preserved since we only ever
move an offset backward to a boundary, never invent a new one.
"""

from __future__ import annotations

import struct


def _snap_to_boundary(data: bytes, offset: int, blob_start: int) -> int:
    """Move `offset` backward to the nearest position that is either the
    very start of the string blob or immediately follows a NUL byte - i.e.
    a real string start. A no-op if `offset` already is one."""
    pos = offset
    while pos > blob_start and data[pos - 1] != 0:
        pos -= 1
    return pos


def _decode(data: bytes, count_fmt: str, offset_fmt: str) -> dict[int, str]:
    count_size = struct.calcsize(count_fmt)
    offset_size = struct.calcsize(offset_fmt)
    if len(data) < count_size:
        return {}
    (count,) = struct.unpack_from(count_fmt, data, 0)
    blob_start = count_size + count * offset_size
    strings: dict[int, str] = {}
    for i in range(count):
        pos = count_size + i * offset_size
        if pos + offset_size > len(data):
            break
        (offset,) = struct.unpack_from(offset_fmt, data, pos)
        if offset == 0:
            continue  # 0 conventionally means "no string" for this id
        if offset >= len(data) or not (offset == blob_start or data[offset - 1] == 0):
            offset = _snap_to_boundary(data, min(offset, len(data)), blob_start)
        end = data.find(b"\x00", offset)
        if end == -1:
            end = len(data)
        raw = data[offset:end]
        # Brood War's string table is in the game's local codepage; latin-1
        # round-trips every byte value so nothing is lost even if this isn't
        # quite the right codepage for the map's actual language.
        strings[i] = raw.decode("latin-1")
    return strings


def decode_str(data: bytes) -> dict[int, str]:
    return _decode(data, "<H", "<H")


def decode_strx(data: bytes) -> dict[int, str]:
    return _decode(data, "<I", "<I")


class StringTable:
    """Combined STR/STRx lookup, matching how the game resolves string ids:
    STRx entries (Remastered / >64KB extended table) take priority, falling
    back to the classic STR table."""

    def __init__(self, chk):
        self.str_strings = decode_str(chk.get("STR ") or b"")
        self.strx_strings = decode_strx(chk.get("STRx") or b"") if "STRx" in chk else {}

    def get(self, string_id: int | None) -> str | None:
        if not string_id:
            return None
        if string_id in self.strx_strings:
            return self.strx_strings[string_id]
        return self.str_strings.get(string_id)

    def __getitem__(self, string_id: int) -> str:
        return self.get(string_id) or ""
