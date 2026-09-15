"""
Minimal MPQ archive *writer* - the inverse of `mpq.py`'s reader.

Storage shape is now confirmed against real data, not guessed: three
independent tools (a real map hand-built in ScmDraft 2, and the source of
both `LangUMS` and `ChkDraft` - two working, real-world map tools, both of
which use StormLib's `SFileCreateFile`/`SFileWriteFile` with just
`MPQ_FILE_COMPRESS`, no `MPQ_FILE_SINGLE_UNIT`) agree: `staredit\\scenario.chk`
is stored **multi-sector**, **PKWARE-implode-compressed**, and
**encrypted**. All three are implemented here, mirroring `mpq.py`'s read
path exactly in reverse - same sector size formula, same per-sector
compression decision, same key derivation (see `_file_key` there).

Compression defaults to PKWARE implode (`pkware_dcl.implode`) - confirmed
via direct byte inspection of a real map (see `.ai/context.md`) that this
is compression type 8, not zlib; an earlier zlib experiment (type 2, also
a real MPQ-supported type) actively regressed an in-progress load attempt.
`compress_zlib` is kept only for comparison/debugging.

What was already true and remains so: the hash table and block table are
always encrypted, with fixed, publicly-known keys (`hash('(hash table)',
'TABLE')` / `hash('(block table)', 'TABLE')`). `_encrypt` is the mirror of
`mpyq`'s `_decrypt` (same stream cipher run forward instead of back -
verified by round-tripping through mpyq's own `_decrypt` before this was
trusted for anything real).

Known limitation, found by testing (not theoretical): per-sector
compression here always uses the compressed form, with no "store raw
instead" fallback for a sector where compression doesn't actually shrink
the data - short/low-redundancy input (plain text under ~50 bytes, e.g.)
can compress *larger* than raw once PKWARE's per-literal overhead and
4-byte encryption padding are added. When that happens, the reader's
decompress-or-not heuristic (`bytes_left > len(sector)` in `mpq.py`) comes
out wrong and returns the still-compressed bytes verbatim as garbage. A
correct general fix needs a raw-sector fallback that *also* survives
`_encrypt`'s 4-byte-block requirement without corrupting output - nontrivial,
since padding a raw (non-self-terminating) sector leaks the pad bytes into
the result the way padding a compressed (self-terminating) one doesn't.
Not fixed: real CHK content (large, repetitive - see `chk_encode.py`'s
PUNI/UPGR/PTEC defaults, mostly zero-fill) reliably compresses well below
raw size in every sector, verified directly against the actual generated
map's CHK bytes before trusting this. Just don't compress/encrypt
something short and unique (`(listfile)`'s own content hit exactly this -
see `scripts/generate_marine_map.py`, which stores it plain instead).
"""

from __future__ import annotations

import struct
import zlib

import mpyq

from . import pkware_dcl

_TABLE = mpyq.MPQArchive.encryption_table  # class attribute, no archive needed

_HASH_TYPES = {"TABLE_OFFSET": 0, "HASH_A": 1, "HASH_B": 2, "TABLE": 3}

MPQ_FILE_COMPRESS = 0x00000200
MPQ_FILE_ENCRYPTED = 0x00010000
MPQ_FILE_EXISTS = 0x80000000
MPQ_FILE_SINGLE_UNIT = 0x01000000

_HASH_ENTRY = struct.Struct("<2I2HI")  # hash_a, hash_b, locale, platform, block_index
_BLOCK_ENTRY = struct.Struct("<4I")  # offset, archived_size, size, flags
_HEADER = struct.Struct("<4s2I2H4I")  # matches mpyq.MPQFileHeader (format_version 0)

EMPTY_HASH_ENTRY = b"\xff" * 16

SECTOR_SIZE_SHIFT = 3  # matches the real reference map's header; sector size = 512 << 3 = 4096


def mpq_hash(s: str, hash_type: str) -> int:
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in s.upper():
        value = _TABLE[(_HASH_TYPES[hash_type] << 8) + ord(ch)]
        seed1 = (value ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (ord(ch) + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1


def _file_key(mpq_path: str) -> int:
    """Mirror of mpq.py's `_file_key`, without the MPQ_FILE_FIX_KEY branch -
    the real reference map doesn't set that flag, so plain
    hash(basename, 'TABLE') is the whole story here."""
    basename = mpq_path.replace("/", "\\").rsplit("\\", 1)[-1]
    return mpq_hash(basename, "TABLE")


def _encrypt(data: bytes, key: int) -> bytes:
    assert len(data) % 4 == 0
    seed1, seed2 = key, 0xEEEEEEEE
    out = bytearray()
    for i in range(len(data) // 4):
        seed2 = (seed2 + _TABLE[0x400 + (seed1 & 0xFF)]) & 0xFFFFFFFF
        plain = struct.unpack_from("<I", data, i * 4)[0]
        cipher = (plain ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed1 = (((~seed1) << 0x15) + 0x11111111) | (seed1 >> 0x0B)
        seed1 &= 0xFFFFFFFF
        seed2 = (plain + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
        out += struct.pack("<I", cipher)
    return bytes(out)


def _pad4(data: bytes) -> bytes:
    """_encrypt operates on whole u32s; pad to a 4-byte boundary. Only ever
    applied to a whole encrypted *unit* (a sector, or the position table),
    never to a sub-slice, so the padding never ends up embedded mid-stream
    for a reader to trip over - it's simply part of that unit's encrypted
    bytes, matching how real per-sector encryption pads (sector payloads
    aren't naturally 4-byte-aligned either)."""
    remainder = len(data) % 4
    return data if remainder == 0 else data + bytes(4 - remainder)


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def compress_pkware(raw: bytes) -> bytes:
    return b"\x08" + pkware_dcl.implode(raw)


def compress_zlib(raw: bytes) -> bytes:
    return b"\x02" + zlib.compress(raw, level=9)


def _store_member(raw: bytes, *, compressor, compress: bool, key: int | None) -> bytes:
    """Build the on-disk (possibly compressed, possibly encrypted)
    multi-sector byte blob for one member, mirroring mpq.py's read path
    (sector_size, position-table-then-sectors layout, key/key+i encryption)
    exactly in reverse."""
    sector_size = 512 << SECTOR_SIZE_SHIFT
    n = len(raw)
    # Mirrors mpq.py's `num_sectors = block.size // sector_size + 1` (and
    # the real format it was read from) - yes, this really does add one
    # trailing empty sector when `n` divides sector_size evenly; matching
    # the reader's own formula matters more here than what looks "tidier".
    num_sectors = n // sector_size + 1
    num_positions = num_sectors + 1

    sectors = []
    for i in range(num_sectors):
        chunk = raw[i * sector_size : (i + 1) * sector_size]
        # The `num_sectors` formula above always allocates one trailing
        # sector beyond a length that divides sector_size evenly, which is
        # genuinely *empty* (chunk == b""). Compressing empty data still
        # emits header+terminator overhead (a few bytes, not zero) -
        # running it through `compressor` would produce a *non-empty*
        # stored sector for conceptually-empty content, and since the
        # reader's decompress-or-not decision (`bytes_left > len(sector)`)
        # sees `bytes_left == 0` for this trailing sector, it always skips
        # decompression and returns that overhead verbatim as trailing
        # garbage. Bypassing the compressor for a genuinely empty chunk
        # keeps the stored sector genuinely empty too. Caught by testing
        # exact-sector-size-multiple inputs before trusting this - see
        # .ai/context.md.
        stored = compressor(chunk) if (compress and chunk) else chunk
        if key is not None:
            # Pad to a 4-byte boundary and keep the padded length (don't
            # truncate back) - `_encrypt`/mpyq's `_decrypt` only process
            # whole u32s and silently *drop* any trailing partial group,
            # so encrypting-then-truncating would lose bytes on the way
            # back out. Keeping the pad means the position table below
            # reflects the true stored length, and `explode()` is
            # self-terminating (stops at its own end marker) so the extra
            # padding bytes after decryption are harmless noise, not data
            # loss. Caught by round-tripping this exact function's output
            # through mpq.py before trusting it - see .ai/context.md.
            stored = _encrypt(_pad4(stored), (key + i) & 0xFFFFFFFF)
        sectors.append(stored)

    positions = [4 * num_positions]
    for s in sectors:
        positions.append(positions[-1] + len(s))
    pos_bytes = struct.pack(f"<{num_positions}I", *positions)
    if key is not None:
        pos_bytes = _encrypt(pos_bytes, (key - 1) & 0xFFFFFFFF)

    return pos_bytes + b"".join(sectors)


def build_mpq(
    members: dict[str, bytes],
    compress: set[str] = frozenset(),
    encrypt: set[str] = frozenset(),
    compressor=compress_pkware,
) -> bytes:
    """Build a minimal, valid MPQ archive holding exactly `members`
    (path -> raw bytes), stored multi-sector. Names in `compress` are
    PKWARE-compressed per sector (pass `compressor=compress_zlib` to
    compare against zlib instead); names in `encrypt` have their sector
    table and sector contents encrypted with the standard per-file key
    (see `_file_key`)."""
    names = list(members.keys())
    n = len(names)
    table_size = max(4, _next_pow2(n * 2))  # headroom to keep collisions cheap

    header_size = _HEADER.size  # 32
    file_offsets: dict[str, int] = {}
    stored_bytes: dict[str, bytes] = {}
    body = bytearray()
    offset = header_size
    for name in names:
        raw = members[name]
        key = _file_key(name) if name in encrypt else None
        stored = _store_member(raw, compressor=compressor, compress=name in compress, key=key)
        stored_bytes[name] = stored
        file_offsets[name] = offset
        body += stored
        offset += len(stored)

    hash_table_offset = offset
    hash_slots: list[bytes | None] = [None] * table_size
    for block_index, name in enumerate(names):
        hash_a = mpq_hash(name, "HASH_A")
        hash_b = mpq_hash(name, "HASH_B")
        slot = mpq_hash(name, "TABLE_OFFSET") % table_size
        while hash_slots[slot] is not None:
            slot = (slot + 1) % table_size
        # locale=0 ("neutral"/default) - a real bug caught by an actual
        # game-load attempt: this was 0xFFFF (the "unused slot" sentinel
        # value) for a while, which `mpyq` happily accepted (it never
        # checks locale) but the retail engine's own file lookup - which
        # requests locale 0 - couldn't match, so it never found
        # staredit\scenario.chk in the archive at all. Round-tripping
        # through our own reader plus plain mpyq caught every *structural*
        # mistake; it took an actual failed load to catch this one.
        hash_slots[slot] = _HASH_ENTRY.pack(hash_a, hash_b, 0, 0, block_index)
    hash_table_plain = b"".join(s if s is not None else EMPTY_HASH_ENTRY for s in hash_slots)
    hash_table = _encrypt(hash_table_plain, mpq_hash("(hash table)", "TABLE"))

    block_table_offset = hash_table_offset + len(hash_table)
    block_entries = bytearray()
    for name in names:
        flags = MPQ_FILE_EXISTS
        if name in compress:
            flags |= MPQ_FILE_COMPRESS
        if name in encrypt:
            flags |= MPQ_FILE_ENCRYPTED
        archived_size = len(stored_bytes[name])
        real_size = len(members[name])
        block_entries += _BLOCK_ENTRY.pack(file_offsets[name], archived_size, real_size, flags)
    block_table = _encrypt(bytes(block_entries), mpq_hash("(block table)", "TABLE"))

    archive_size = block_table_offset + len(block_table)
    header = _HEADER.pack(
        b"MPQ\x1a",
        header_size,
        archive_size,
        0,  # format_version
        SECTOR_SIZE_SHIFT,
        hash_table_offset,
        block_table_offset,
        table_size,
        n,
    )

    return bytes(header) + bytes(body) + hash_table + block_table
