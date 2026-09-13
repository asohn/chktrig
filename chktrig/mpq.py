"""
Minimal MPQ archive reader, just enough to pull `staredit\\scenario.chk`
(and other member files) out of a StarCraft .scx/.scm map.

Built on top of `mpyq` for header/hash-table/block-table parsing and the
shared MPQ encryption table, but replaces mpyq's `read_file` because mpyq
0.2.5 doesn't implement per-file decryption (`MPQ_FILE_ENCRYPTED` just
raises NotImplementedError) - and real Brood War maps routinely store
`(listfile)` and `staredit\\scenario.chk` encrypted.

Algorithm (standard MoPaQ format, unchanged from Blizzard's original spec):
  - file_key = mpq_hash(basename(member_path), 'TABLE')
  - if MPQ_FILE_FIX_KEY: file_key = (file_key + block.offset) ^ block.size
  - multi-sector files store a (sector_count + 1)-entry u32 offset table
    before the sector data; that table is itself encrypted with
    (file_key - 1), and sector i's data is encrypted with (file_key + i).
  - single-unit files are decrypted directly with file_key.

Compression: sector/file data may additionally be compressed. StarCraft
uses PKWARE DCL "implode" (type byte 0x08) for scenario.chk - see
pkware_dcl.py - alongside the zlib/bz2 mpyq already handles.
"""

from __future__ import annotations

import bz2
import zlib
from io import BytesIO
from pathlib import Path

import mpyq

from . import pkware_dcl

MPQ_FILE_IMPLODE = 0x00000100
MPQ_FILE_COMPRESS = 0x00000200
MPQ_FILE_ENCRYPTED = 0x00010000
MPQ_FILE_FIX_KEY = 0x00020000
MPQ_FILE_SINGLE_UNIT = 0x01000000
MPQ_FILE_SECTOR_CRC = 0x04000000
MPQ_FILE_EXISTS = 0x80000000


class MPQError(Exception):
    pass


def _decompress_block(data: bytes) -> bytes:
    """Decompress a single MPQ-compressed block (one leading type byte)."""
    if not data:
        return data
    compression_type = data[0]
    if compression_type == 0:
        return data[1:]
    if compression_type == 2:
        return zlib.decompress(data[1:], 15)
    if compression_type == 8:
        return pkware_dcl.explode(data[1:])
    if compression_type == 16:
        return bz2.decompress(data[1:])
    raise MPQError(f"unsupported MPQ sector compression type {compression_type:#x}")


def _file_key(archive: mpyq.MPQArchive, member_path: bytes, block) -> int:
    basename = member_path.replace(b"/", b"\\").rsplit(b"\\", 1)[-1]
    key = archive._hash(basename.decode("ascii", "replace"), "TABLE")
    if block.flags & MPQ_FILE_FIX_KEY:
        key = (key + block.offset) ^ block.size
        key &= 0xFFFFFFFF
    return key


def read_member(archive: mpyq.MPQArchive, member_path: bytes) -> bytes | None:
    """Read and fully decrypt/decompress one member file from an open archive."""
    if isinstance(member_path, str):
        member_path = member_path.encode("ascii")

    hash_entry = archive.get_hash_table_entry(member_path)
    if hash_entry is None:
        return None
    block = archive.block_table[hash_entry.block_table_index]
    if not (block.flags & MPQ_FILE_EXISTS) or block.archived_size == 0:
        return None

    archive.file.seek(block.offset + archive.header["offset"])
    raw = archive.file.read(block.archived_size)

    key = None
    if block.flags & MPQ_FILE_ENCRYPTED:
        key = _file_key(archive, member_path, block)

    if block.flags & MPQ_FILE_SINGLE_UNIT:
        if key is not None:
            raw = archive._decrypt(raw, key)
        if block.flags & MPQ_FILE_COMPRESS and block.size > block.archived_size:
            raw = _decompress_block(raw)
        return raw

    sector_size = 512 << archive.header["sector_size_shift"]
    num_sectors = block.size // sector_size + 1
    num_positions = num_sectors + 1
    if block.flags & MPQ_FILE_SECTOR_CRC:
        num_positions += 1

    pos_bytes = raw[: 4 * num_positions]
    if key is not None:
        pos_bytes = archive._decrypt(pos_bytes, (key - 1) & 0xFFFFFFFF)
    import struct

    positions = struct.unpack(f"<{num_positions}I", pos_bytes)

    out = BytesIO()
    bytes_left = block.size
    n_data_sectors = len(positions) - (2 if (block.flags & MPQ_FILE_SECTOR_CRC) else 1)
    for i in range(n_data_sectors):
        sector = raw[positions[i] : positions[i + 1]]
        if key is not None:
            sector = archive._decrypt(sector, (key + i) & 0xFFFFFFFF)
        if block.flags & MPQ_FILE_COMPRESS and bytes_left > len(sector):
            sector = _decompress_block(sector)
        bytes_left -= len(sector)
        out.write(sector)
    return out.getvalue()


def open_archive(path: str | Path) -> mpyq.MPQArchive:
    """Open an MPQ archive (e.g. a .scx/.scm map) without touching (listfile)."""
    return mpyq.MPQArchive(str(path), listfile=False)


def extract_scenario_chk(path: str | Path) -> bytes:
    """Extract and decompress `staredit\\scenario.chk` from a .scx/.scm map."""
    archive = open_archive(path)
    data = read_member(archive, b"staredit\\scenario.chk")
    if data is None:
        raise MPQError(f"{path}: no staredit\\scenario.chk member found")
    return data
