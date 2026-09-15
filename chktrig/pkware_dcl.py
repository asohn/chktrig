"""
PKWARE Data Compression Library (DCL) "implode"/"explode" codec.

StarCraft's MPQ archives compress most files (including staredit\\scenario.chk)
with PKWARE DCL implode rather than zlib/deflate, so Python's stdlib `zlib`
module can't touch it. There's no maintained PyPI package for this either, so
this is a from-scratch Python 3 port of the well-known reference algorithm:

    SComp (Ladislav Zezula / StormLib) - a reimplementation of PKWARE Data
    Compression Library for Win32 (PKWARE Inc., 1989-1995, patent 5,051,745).

Ported here from PyMS's Python port of the same reference (PyMS is a widely
used, actively maintained StarCraft modding suite):
https://github.com/poiuyqwert/PyMS/blob/master/PyMS/FileFormats/MPQ/PQmpq/MPQComp/pkware.py

Only `explode` (decompress) is implemented for now, since this project's
first goal is reading/analyzing triggers, not writing modified maps back.
"""

from __future__ import annotations


# --- static tables (from the PKWARE DCL reference implementation) ---------

_DIST_BITS = (
    0x02, 0x04, 0x04, 0x05, 0x05, 0x05, 0x05, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
    0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
    0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08,
)

_DIST_CODE = (
    0x03, 0x0D, 0x05, 0x19, 0x09, 0x11, 0x01, 0x3E, 0x1E, 0x2E, 0x0E, 0x36, 0x16, 0x26, 0x06, 0x3A,
    0x1A, 0x2A, 0x0A, 0x32, 0x12, 0x22, 0x42, 0x02, 0x7C, 0x3C, 0x5C, 0x1C, 0x6C, 0x2C, 0x4C, 0x0C,
    0x74, 0x34, 0x54, 0x14, 0x64, 0x24, 0x44, 0x04, 0x78, 0x38, 0x58, 0x18, 0x68, 0x28, 0x48, 0x08,
    0xF0, 0x70, 0xB0, 0x30, 0xD0, 0x50, 0x90, 0x10, 0xE0, 0x60, 0xA0, 0x20, 0xC0, 0x40, 0x80, 0x00,
)

_EX_LEN_BITS = (
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
)

_LEN_BASE = (
    0x0000, 0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007,
    0x0008, 0x000A, 0x000E, 0x0016, 0x0026, 0x0046, 0x0086, 0x0106,
)

_LEN_BITS = (
    0x03, 0x02, 0x03, 0x03, 0x04, 0x04, 0x04, 0x05, 0x05, 0x05, 0x05, 0x06, 0x06, 0x06, 0x07, 0x07,
)

_LEN_CODE = (
    0x05, 0x03, 0x01, 0x06, 0x0A, 0x02, 0x0C, 0x14, 0x04, 0x18, 0x08, 0x30, 0x10, 0x20, 0x40, 0x00,
)

_CH_BITS_ASC = [
    0x0B, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x08, 0x07, 0x0C, 0x0C, 0x07, 0x0C, 0x0C,
    0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0D, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C,
    0x04, 0x0A, 0x08, 0x0C, 0x0A, 0x0C, 0x0A, 0x08, 0x07, 0x07, 0x08, 0x09, 0x07, 0x06, 0x07, 0x08,
    0x07, 0x06, 0x07, 0x07, 0x07, 0x07, 0x08, 0x07, 0x07, 0x08, 0x08, 0x0C, 0x0B, 0x07, 0x09, 0x0B,
    0x0C, 0x06, 0x07, 0x06, 0x06, 0x05, 0x07, 0x08, 0x08, 0x06, 0x0B, 0x09, 0x06, 0x07, 0x06, 0x06,
    0x07, 0x0B, 0x06, 0x06, 0x06, 0x07, 0x09, 0x08, 0x09, 0x09, 0x0B, 0x08, 0x0B, 0x09, 0x0C, 0x08,
    0x0C, 0x05, 0x06, 0x06, 0x06, 0x05, 0x06, 0x06, 0x06, 0x05, 0x0B, 0x07, 0x05, 0x06, 0x05, 0x05,
    0x06, 0x0A, 0x05, 0x05, 0x05, 0x05, 0x08, 0x07, 0x08, 0x08, 0x0A, 0x0B, 0x0B, 0x0C, 0x0C, 0x0C,
    0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D,
    0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D,
    0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D,
    0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C,
    0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C,
    0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C,
    0x0D, 0x0C, 0x0D, 0x0D, 0x0D, 0x0C, 0x0D, 0x0D, 0x0D, 0x0C, 0x0D, 0x0D, 0x0D, 0x0D, 0x0C, 0x0D,
    0x0D, 0x0D, 0x0C, 0x0C, 0x0C, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D, 0x0D,
]

_CH_CODE_ASC = (
    0x0490, 0x0FE0, 0x07E0, 0x0BE0, 0x03E0, 0x0DE0, 0x05E0, 0x09E0,
    0x01E0, 0x00B8, 0x0062, 0x0EE0, 0x06E0, 0x0022, 0x0AE0, 0x02E0,
    0x0CE0, 0x04E0, 0x08E0, 0x00E0, 0x0F60, 0x0760, 0x0B60, 0x0360,
    0x0D60, 0x0560, 0x1240, 0x0960, 0x0160, 0x0E60, 0x0660, 0x0A60,
    0x000F, 0x0250, 0x0038, 0x0260, 0x0050, 0x0C60, 0x0390, 0x00D8,
    0x0042, 0x0002, 0x0058, 0x01B0, 0x007C, 0x0029, 0x003C, 0x0098,
    0x005C, 0x0009, 0x001C, 0x006C, 0x002C, 0x004C, 0x0018, 0x000C,
    0x0074, 0x00E8, 0x0068, 0x0460, 0x0090, 0x0034, 0x00B0, 0x0710,
    0x0860, 0x0031, 0x0054, 0x0011, 0x0021, 0x0017, 0x0014, 0x00A8,
    0x0028, 0x0001, 0x0310, 0x0130, 0x003E, 0x0064, 0x001E, 0x002E,
    0x0024, 0x0510, 0x000E, 0x0036, 0x0016, 0x0044, 0x0030, 0x00C8,
    0x01D0, 0x00D0, 0x0110, 0x0048, 0x0610, 0x0150, 0x0060, 0x0088,
    0x0FA0, 0x0007, 0x0026, 0x0006, 0x003A, 0x001B, 0x001A, 0x002A,
    0x000A, 0x000B, 0x0210, 0x0004, 0x0013, 0x0032, 0x0003, 0x001D,
    0x0012, 0x0190, 0x000D, 0x0015, 0x0005, 0x0019, 0x0008, 0x0078,
    0x00F0, 0x0070, 0x0290, 0x0410, 0x0010, 0x07A0, 0x0BA0, 0x03A0,
    0x0240, 0x1C40, 0x0C40, 0x1440, 0x0440, 0x1840, 0x0840, 0x1040,
    0x0040, 0x1F80, 0x0F80, 0x1780, 0x0780, 0x1B80, 0x0B80, 0x1380,
    0x0380, 0x1D80, 0x0D80, 0x1580, 0x0580, 0x1980, 0x0980, 0x1180,
    0x0180, 0x1E80, 0x0E80, 0x1680, 0x0680, 0x1A80, 0x0A80, 0x1280,
    0x0280, 0x1C80, 0x0C80, 0x1480, 0x0480, 0x1880, 0x0880, 0x1080,
    0x0080, 0x1F00, 0x0F00, 0x1700, 0x0700, 0x1B00, 0x0B00, 0x1300,
    0x0DA0, 0x05A0, 0x09A0, 0x01A0, 0x0EA0, 0x06A0, 0x0AA0, 0x02A0,
    0x0CA0, 0x04A0, 0x08A0, 0x00A0, 0x0F20, 0x0720, 0x0B20, 0x0320,
    0x0D20, 0x0520, 0x0920, 0x0120, 0x0E20, 0x0620, 0x0A20, 0x0220,
    0x0C20, 0x0420, 0x0820, 0x0020, 0x0FC0, 0x07C0, 0x0BC0, 0x03C0,
    0x0DC0, 0x05C0, 0x09C0, 0x01C0, 0x0EC0, 0x06C0, 0x0AC0, 0x02C0,
    0x0CC0, 0x04C0, 0x08C0, 0x00C0, 0x0F40, 0x0740, 0x0B40, 0x0340,
    0x0300, 0x0D40, 0x1D00, 0x0D00, 0x1500, 0x0540, 0x0500, 0x1900,
    0x0900, 0x0940, 0x1100, 0x0100, 0x1E00, 0x0E00, 0x0140, 0x1600,
    0x0600, 0x1A00, 0x0E40, 0x0640, 0x0A40, 0x0A00, 0x1200, 0x0200,
    0x1C00, 0x0C00, 0x1400, 0x0400, 0x1800, 0x0800, 0x1000, 0x0000,
)


class PKDCLError(Exception):
    pass


def _gen_decode_table(count, bits_table, code_table):
    positions = [0] * 0x100
    for index in range(count - 1, -1, -1):
        code = code_table[index]
        step = 1 << bits_table[index]
        for pos in range(code, 0x100, step):
            positions[pos] = index
    return tuple(positions)


_POSITION1 = _gen_decode_table(0x40, _DIST_BITS, _DIST_CODE)
_POSITION2 = _gen_decode_table(0x10, _LEN_BITS, _LEN_CODE)


def _gen_ascii_tables():
    ch_bits_asc = list(_CH_BITS_ASC)
    offs2c34 = [0] * 0x100
    offs2d34 = [0] * 0x100
    offs2e34 = [0] * 0x80
    offs2eb4 = [0] * 0x100
    for index in range(0xFF, -1, -1):
        bits = ch_bits_asc[index]
        acc = _CH_CODE_ASC[index]
        if bits <= 8:
            add = 1 << bits
            for pos in range(acc, 0x100, add):
                offs2c34[pos] = index
        elif acc & 0xFF:
            offs2c34[acc & 0xFF] = 0xFF
            if acc & 0x3F:
                bits -= 4
                ch_bits_asc[index] = bits
                add = 1 << bits
                acc >>= 4
                for pos in range(acc, 0x100, add):
                    offs2d34[pos] = index
            else:
                bits -= 6
                ch_bits_asc[index] = bits
                add = 1 << bits
                acc >>= 6
                for pos in range(acc, 0x80, add):
                    offs2e34[pos] = index
        else:
            bits -= 8
            ch_bits_asc[index] = bits
            add = 1 << bits
            acc >>= 8
            for pos in range(acc, 0x100, add):
                offs2eb4[pos] = index
    return tuple(ch_bits_asc), tuple(offs2c34), tuple(offs2d34), tuple(offs2e34), tuple(offs2eb4)


# binary(0) mode never needs the ascii tables; build lazily on first use.
_ASCII_TABLES = None


def _ascii_tables():
    global _ASCII_TABLES
    if _ASCII_TABLES is None:
        _ASCII_TABLES = _gen_ascii_tables()
    return _ASCII_TABLES


_COMP_BINARY = 0
_COMP_ASCII = 1

_LIT_DONE = 0
_LIT_BYTE = 1
_LIT_COPY = 2


class _InputExhausted(Exception):
    pass


class _Exploder:
    """One-shot bit-stream decoder for a single PKWARE DCL imploded block."""

    __slots__ = (
        "data", "offset", "comp_type", "dsize_bits", "dsize_mask",
        "bit_buff", "extra_bits", "ch_bits_asc", "offs2c34", "offs2d34",
        "offs2e34", "offs2eb4",
    )

    def __init__(self, data: bytes):
        if len(data) < 4:
            raise PKDCLError(f"not enough data to explode (got {len(data)} bytes, need >= 4)")
        self.data = data
        self.comp_type = data[0]
        self.dsize_bits = data[1]
        self.bit_buff = data[2]
        self.offset = 3

        if not (4 <= self.dsize_bits <= 6):
            raise PKDCLError(f"invalid dictionary size bits (got {self.dsize_bits}, need 4-6)")
        if self.comp_type not in (_COMP_BINARY, _COMP_ASCII):
            raise PKDCLError(f"invalid compression type (got {self.comp_type}, need 0 or 1)")
        if self.comp_type == _COMP_ASCII:
            self.ch_bits_asc, self.offs2c34, self.offs2d34, self.offs2e34, self.offs2eb4 = _ascii_tables()

        self.dsize_mask = 0xFFFF >> (0x10 - self.dsize_bits)
        self.extra_bits = 0

    def _read_byte(self) -> int:
        if self.offset >= len(self.data):
            raise _InputExhausted()
        b = self.data[self.offset]
        self.offset += 1
        return b

    def _waste_bits(self, bits: int) -> None:
        if bits <= self.extra_bits:
            self.extra_bits -= bits
            self.bit_buff >>= bits
        else:
            self.bit_buff >>= self.extra_bits
            self.bit_buff |= self._read_byte() << 8
            self.bit_buff >>= bits - self.extra_bits
            self.extra_bits = (self.extra_bits - bits) + 8

    def _decode_lit(self):
        lit_copy = self.bit_buff & 1
        self._waste_bits(1)
        if lit_copy:
            value = _POSITION2[self.bit_buff & 0xFF]
            self._waste_bits(_LEN_BITS[value])
            bits = _EX_LEN_BITS[value]
            if bits != 0:
                value2 = self.bit_buff & ((1 << bits) - 1)
                try:
                    self._waste_bits(bits)
                except _InputExhausted:
                    if (value + value2) != 0x10E:
                        raise
                value = _LEN_BASE[value] + value2
                if value == 0x205:
                    return (_LIT_DONE, None)
            return (_LIT_COPY, value + 2)

        if self.comp_type == _COMP_BINARY:
            value = self.bit_buff & 0xFF
            self._waste_bits(8)
            return (_LIT_BYTE, value)

        if self.bit_buff & 0xFF:
            value = self.offs2c34[self.bit_buff & 0xFF]
            if value == 0xFF:
                if self.bit_buff & 0x3F:
                    self._waste_bits(4)
                    value = self.offs2d34[self.bit_buff & 0xFF]
                else:
                    self._waste_bits(6)
                    value = self.offs2e34[self.bit_buff & 0x7F]
        else:
            self._waste_bits(8)
            value = self.offs2eb4[self.bit_buff & 0xFF]
        self._waste_bits(self.ch_bits_asc[value])
        return (_LIT_BYTE, value)

    def _decode_dist(self, length: int) -> int:
        pos = _POSITION1[self.bit_buff & 0xFF]
        skip = _DIST_BITS[pos]
        self._waste_bits(skip)
        if length == 2:
            pos = (pos << 2) | (self.bit_buff & 0x03)
            self._waste_bits(2)
        else:
            pos = (pos << self.dsize_bits) | (self.bit_buff & self.dsize_mask)
            self._waste_bits(self.dsize_bits)
        return pos + 1

    def expand(self) -> bytes:
        out = bytearray()
        try:
            while True:
                lit, value = self._decode_lit()
                if lit == _LIT_DONE:
                    break
                elif lit == _LIT_COPY:
                    move_back = self._decode_dist(value)
                    remaining = value
                    while remaining > 0:
                        copy_size = min(move_back, remaining)
                        start = len(out) - move_back
                        out += out[start:start + copy_size]
                        remaining -= copy_size
                else:
                    out.append(value)
        except _InputExhausted:
            pass
        return bytes(out)


def explode(data: bytes) -> bytes:
    """Decompress ("explode") a single PKWARE DCL imploded block."""
    return _Exploder(data).expand()


# --- implode (compress) -----------------------------------------------------
#
# Ported from the match-finding *shape* (not the sophisticated hash/lookahead
# machinery) of the reference implementation: StormLib's src/pklib/implode.c
# (github.com/ladislav-zezula/StormLib, Copyright Ladislav Zezula). That
# source's `FindRep`/`SortBuffer` build an elaborate PAIR_HASH index for
# near-optimal match selection; this is a much simpler greedy hash-chain
# matcher instead - it doesn't compress as tightly, but produces output that
# is bit-for-bit *decodable* by the same fixed code tables `explode` (and the
# real game) use, which is the only thing that actually matters for a
# roundtrip. Verified by exploding our own implode() output and comparing
# against the original - see scripts/ and the session that added this.
#
# Format recap (mirrors `_Exploder` above, run backwards): byte0 = comp_type,
# byte1 = dsize_bits, then a LSB-first bitstream of the SAME 9-bit binary-
# mode literals / length+distance copy codes `_Exploder` decodes, terminated
# by a specific maximum-length code (0x305 in the reference's code-table
# indexing) that decodes to the value 0x205 - `_Exploder.decode_lit`'s DONE
# sentinel.

MAX_MATCH_LENGTH = 0x204  # 516 - matches MAX_REP_LENGTH in the reference
_MIN_MATCH_LENGTH = 2

# CMP_IMPLODE_DICT_SIZE3 in pklib.h: the largest standard window (0x1000
# bytes) - gives matches the most reach, which matters for the kind of
# large repeated runs (all-default tables, blank trigger slots) real CHK
# sections are full of.
DICT_SIZE = 0x1000
DSIZE_BITS = 6
DSIZE_MASK = 0x3F

_COMP_TYPE_BINARY = 0


class _BitWriter:
    """LSB-first bit accumulator - the write-side mirror of `_Exploder`'s
    `bit_buff`/`_waste_bits` (which consumes bits LSB-first per byte)."""

    __slots__ = ("out", "acc", "nbits")

    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.nbits = 0

    def write(self, nbits: int, value: int) -> None:
        self.acc |= (value & ((1 << nbits) - 1)) << self.nbits
        self.nbits += nbits
        while self.nbits >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.nbits -= 8

    def getvalue(self) -> bytes:
        if self.nbits > 0:
            self.out.append(self.acc & 0xFF)
        return bytes(self.out)


def _length_code(match_len: int) -> tuple[int, int]:
    """Map a match length (2..MAX_MATCH_LENGTH) to (group_index, extra_bits_value)."""
    raw = match_len - 2
    for i in range(15, -1, -1):
        if _LEN_BASE[i] <= raw:
            return i, raw - _LEN_BASE[i]
    raise AssertionError(f"length {match_len} out of range")  # pragma: no cover


def _emit_literal(bw: _BitWriter, byte: int) -> None:
    # Binary-mode literal: 9 bits, code = byte*2 (bit0=0 -> "not a copy",
    # bits1-8 -> the raw byte value) - matches _Exploder's `comp_type ==
    # _COMP_BINARY` branch of decode_lit exactly.
    bw.write(9, byte * 2)


def _emit_copy(bw: _BitWriter, match_len: int, distance: int) -> None:
    group, extra = _length_code(match_len)
    code = (extra << (_LEN_BITS[group] + 1)) | (_LEN_CODE[group] * 2) | 1
    bits = _EX_LEN_BITS[group] + _LEN_BITS[group] + 1
    bw.write(bits, code)

    d = distance - 1  # the format stores backward distance decremented by 1
    if match_len == 2:
        pos = d >> 2
        bw.write(_DIST_BITS[pos], _DIST_CODE[pos])
        bw.write(2, d & 3)
    else:
        pos = d >> DSIZE_BITS
        bw.write(_DIST_BITS[pos], _DIST_CODE[pos])
        bw.write(DSIZE_BITS, d & DSIZE_MASK)


def _emit_terminator(bw: _BitWriter) -> None:
    # The reference encodes this as nChCodes[0x305]/nChBits[0x305] - the
    # very last sub-code of the largest length group (group 15, extra-bits
    # value 255), which happens to decode to LEN_BASE[15] + 255 == 0x205,
    # _Exploder.decode_lit's DONE sentinel. Precomputed by hand from
    # implode.c's table-building loop rather than reimplementing that whole
    # loop for one fixed value: group=15 has LEN_BITS=7, LEN_CODE=0, so
    # bits = 8 (EX_LEN_BITS[15]) + 7 + 1 = 16, code = (255<<8)|(0*2)|1 = 0xFF01.
    assert _LEN_BITS[15] == 7 and _LEN_CODE[15] == 0 and _EX_LEN_BITS[15] == 8
    bw.write(16, 0xFF01)


def _find_match(data: bytes, i: int, n: int, table: dict[int, list[int]]) -> tuple[int, int]:
    """Greedy hash-chain match finder. Returns (length, distance), (0, 0) if
    no usable match. Only 3+-byte prefixes are indexed (shorter matches
    aren't worth a copy code over 1-2 literals anyway)."""
    if i + 3 > n:
        return 0, 0
    key = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
    candidates = table.get(key)
    if not candidates:
        return 0, 0
    limit = i - DICT_SIZE
    max_len = min(MAX_MATCH_LENGTH, n - i)
    best_len, best_dist = 0, 0
    # Most-recent-first: prefers shorter distances on a length tie, which is
    # cheaper to encode and, more importantly, keeps candidate distances
    # within DICT_SIZE more often.
    for j in reversed(candidates):
        if j < limit:
            break
        length = 0
        while length < max_len and data[j + length] == data[i + length]:
            length += 1
        if length > best_len:
            best_len, best_dist = length, i - j
            if best_len >= max_len:
                break
    return best_len, best_dist


_HASH_BUCKET_LIMIT = 32  # cap per-hash candidate list length, bound match-finding cost


def _index_position(data: bytes, i: int, n: int, table: dict[int, list[int]]) -> None:
    if i + 3 > n:
        return
    key = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
    bucket = table.setdefault(key, [])
    bucket.append(i)
    if len(bucket) > _HASH_BUCKET_LIMIT:
        del bucket[0]


def implode(data: bytes) -> bytes:
    """Compress ("implode") data into a PKWARE DCL block `explode` (and the
    real game) can decode. See module-level comment above for what's
    simplified relative to the reference implementation (compression ratio
    only - output is fully valid DCL data)."""
    n = len(data)
    bw = _BitWriter()
    table: dict[int, list[int]] = {}

    i = 0
    while i < n:
        length, distance = _find_match(data, i, n, table)
        if length >= _MIN_MATCH_LENGTH and not (length == 2 and distance > 0x100):
            _emit_copy(bw, length, distance)
            end = i + length
            while i < end:
                _index_position(data, i, n, table)
                i += 1
        else:
            _emit_literal(bw, data[i])
            _index_position(data, i, n, table)
            i += 1

    _emit_terminator(bw)
    return bytes([_COMP_TYPE_BINARY, DSIZE_BITS]) + bw.getvalue()
