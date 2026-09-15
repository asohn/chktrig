"""
Decode the MRGN (locations) section referenced by trigger conditions/actions.

Each location is a fixed 20-byte record: 4x u32 (left, top, right, bottom in
pixels) + u16 string id (its name) + u16 elevation flags. MRGN holds a fixed
array (64 locations pre-1.04 maps, 255 for 1.04+ - we don't need to know
which, we just decode however many whole 20-byte records are present).

Location id 63 ("Location 64" in the editor's 1-based display) is the
special "Anywhere" location baked into every map by StarEdit; the trigger
struct fields use one-off-by-one location numbering (raw value 0 = "no
location", raw value N -> location index N-1), which decoders.py handles -
this module just exposes locations by their raw 0-based index.

Source: PyMS's CHKSectionMRGN.py (github.com/poiuyqwert/PyMS).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

ANYWHERE_INDEX = 63


@dataclass
class Location:
    index: int
    left: int
    top: int
    right: int
    bottom: int
    name_string_id: int
    elevation_flags: int

    def in_use(self) -> bool:
        return bool(
            self.name_string_id or self.left or self.top or self.right or self.bottom
        )

    def encode(self) -> bytes:
        return struct.pack(
            "<4LHH", self.left, self.top, self.right, self.bottom,
            self.name_string_id, self.elevation_flags,
        )


# 255 slots for version >= SC104 (matches CHKSectionMRGN.process_data's own
# rule: `255 if ver.version >= SC104 else 64`); we only ever target the
# modern/BroodWar format here, so always pad to the larger count.
MRGN_SLOT_COUNT = 255


def encode_mrgn(locations: list[Location], slot_count: int = MRGN_SLOT_COUNT) -> bytes:
    by_index = {loc.index: loc for loc in locations}
    out = bytearray()
    for i in range(slot_count):
        loc = by_index.get(i) or Location(i, 0, 0, 0, 0, 0, 0)
        out += loc.encode()
    return bytes(out)


def decode_mrgn(data: bytes) -> list[Location]:
    locations = []
    record_size = 20
    for i in range(len(data) // record_size):
        off = i * record_size
        left, top, right, bottom, name_id, elevation = struct.unpack_from(
            "<4LHH", data, off
        )
        locations.append(Location(i, left, top, right, bottom, name_id, elevation))
    return locations
