"""
Round-trip tests for building an MPQ archive (chktrig/mpq_write.py) and
reading it back (chktrig/mpq.py).

Every case here corresponds to a real bug found during development (see
.ai/context.md's "Marine Walk" entries) - each one passed every check
that existed *before* it was found, so this suite exists specifically to
stop them coming back, not because they seemed likely to recur on their
own.

Test data note: most cases here deliberately stay realistically
*compressible* (long runs, like real CHK sections full of zero-fill and
repetition) rather than fully random. That's not just style - a sector
that fails to compress smaller than its raw size hits a real, documented,
unfixed limitation in mpq_write.py's decompress-or-not heuristic (see its
module docstring and test_known_limitation_incompressible_sector below).
Using realistic data in the general round-trip tests keeps them testing
what they're meant to (container/sector/encryption correctness), not
accidentally re-demonstrating that known gap on every run.
"""

import os

import pytest

from chktrig import mpq, mpq_write

MPQ_PATH = "staredit\\scenario.chk"


def build_and_readback(tmp_path, data: bytes, *, compress: bool = True, encrypt: bool = True) -> bytes:
    members = {MPQ_PATH: data, "(listfile)": b"staredit\\scenario.chk\r\n"}
    names = {MPQ_PATH} if (compress or encrypt) else set()
    archive_bytes = mpq_write.build_mpq(
        members,
        compress=names if compress else set(),
        encrypt=names if encrypt else set(),
    )
    scx_path = tmp_path / "test.scx"
    scx_path.write_bytes(archive_bytes)
    return mpq.extract_scenario_chk(str(scx_path))


@pytest.mark.parametrize("compress", [False, True], ids=["uncompressed", "pkware-compressed"])
@pytest.mark.parametrize("encrypt", [False, True], ids=["unencrypted", "encrypted"])
def test_roundtrip_basic(tmp_path, compress: bool, encrypt: bool) -> None:
    data = b"\x00" * 5700 + b"\x03" * 1748 + b"\x01" * 200
    assert build_and_readback(tmp_path, data, compress=compress, encrypt=encrypt) == data


def test_roundtrip_exact_sector_multiple(tmp_path) -> None:
    # Regression: a length that divides the 4096-byte sector size evenly
    # allocates one genuinely-empty trailing sector (mirrors mpq.py's own
    # `size // sector_size + 1` read-side formula). Compressing that empty
    # chunk used to emit non-empty header+terminator overhead, which the
    # reader's decompress-or-not heuristic then returned verbatim as
    # trailing garbage.
    data = b"\x00" * 3596 + b"A" * 500  # exactly one sector, 4096 bytes
    assert build_and_readback(tmp_path, data) == data

    data_two_sectors = b"\x00" * 4096 + b"\x01" * 4096  # exactly two sectors, 8192 bytes
    assert build_and_readback(tmp_path, data_two_sectors) == data_two_sectors


def test_roundtrip_multi_sector(tmp_path) -> None:
    data = b"X" * 3000 + b"Y" * 5000  # spans 2 sectors, neither exact
    assert build_and_readback(tmp_path, data) == data


def test_roundtrip_real_chk_shaped_content(tmp_path) -> None:
    # Mirrors the actual shape of generated CHK data: mostly zero-fill/
    # repetition (PUNI/UPGR-style filler) with a modest amount of denser,
    # less-compressible content (STR/TRIG-style) mixed in - not pure
    # zeros, but nothing that dominates an entire 4096-byte sector either.
    data = (b"\x00" * 5700 + b"\x03" * 1748 + b"\x01" * 5700) * 2 + os.urandom(300)
    assert build_and_readback(tmp_path, data) == data


def test_encrypted_sector_padding_is_not_lost(tmp_path) -> None:
    # Regression: encrypting a sector whose compressed length isn't a
    # multiple of 4 requires padding before `_encrypt` (which only
    # processes whole u32s); the first version of this padded, encrypted,
    # then *truncated back* to the original length - silently dropping
    # bytes on the way back out, since the reader has no way to know
    # where the "real" data ends inside a decrypted block. Deliberately
    # picks a size whose compressed length is very unlikely to happen to
    # land on a 4-byte boundary.
    data = b"The quick brown fox jumps over the lazy dog. " * 37  # 1739 bytes, not neatly aligned
    assert build_and_readback(tmp_path, data, compress=True, encrypt=True) == data


def test_plain_mpyq_can_open_the_container(tmp_path) -> None:
    # A second, independent reader (not our own mpq.py) should still be
    # able to open the archive and find the member - confirms the
    # container-level structure (header, hash table, block table) is
    # correct independent of whether the reader can decompress PKWARE
    # content itself (mpyq can't).
    import mpyq

    members = {MPQ_PATH: b"\x00" * 6000, "(listfile)": b"staredit\\scenario.chk\r\n"}
    archive_bytes = mpq_write.build_mpq(members, compress={MPQ_PATH}, encrypt={MPQ_PATH})
    scx_path = tmp_path / "test.scx"
    scx_path.write_bytes(archive_bytes)

    archive = mpyq.MPQArchive(str(scx_path), listfile=False)
    try:
        assert archive.get_hash_table_entry(MPQ_PATH.encode()) is not None
    finally:
        # mpyq never closes its own file handle - do it ourselves so
        # pytest's tmp_path cleanup doesn't hit a Windows file-lock error.
        archive.file.close()


@pytest.mark.xfail(strict=True, reason=(
    "Known, documented, unfixed limitation (see mpq_write.py's module "
    "docstring): a sector that compresses *larger* than raw (short, "
    "low-redundancy content) breaks the reader's decompress-or-not "
    "heuristic. Real CHK content never triggers this in practice "
    "(verified directly against generate_marine_map.py's actual output), "
    "so this is deliberately not fixed - this test exists so that IF it "
    "ever starts passing (i.e. someone fixes the general case), that's "
    "flagged as a real, notable change rather than going unnoticed."
))
def test_known_limitation_incompressible_sector(tmp_path) -> None:
    data = os.urandom(4096)  # a full sector of high-entropy data
    assert build_and_readback(tmp_path, data) == data
