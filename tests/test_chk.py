"""
Round-trip and resync tests for chktrig/chk.py.
"""

from chktrig import chk, chk_encode


def test_build_and_parse_roundtrip() -> None:
    sections = [
        (b"VER ", b"\xce\x00"),
        (b"TYPE", b"RAWB"),
        (b"TRIG", b"\x00" * 2400),
    ]
    data = chk_encode.build_chk(sections)
    parsed = chk.parse(data)

    assert parsed.resynced == []
    assert parsed.get("VER ") == b"\xce\x00"
    assert parsed.get(b"TYPE") == b"RAWB"
    assert parsed.get("TRIG") == b"\x00" * 2400


def test_get_returns_none_for_missing_section() -> None:
    parsed = chk.parse(chk_encode.build_chk([(b"VER ", b"\xce\x00")]))
    assert parsed.get("TRIG") is None
    assert "TRIG" not in parsed


def test_last_occurrence_wins_for_duplicate_tags() -> None:
    data = chk_encode.build_chk([(b"STR ", b"first"), (b"STR ", b"second")])
    parsed = chk.parse(data)
    assert parsed.get("STR ") == b"second"
    assert parsed.section_order == [b"STR ", b"STR "]


def test_tag_requires_exact_match_including_trailing_space() -> None:
    # A documented gotcha (see README) - worth pinning down as a real test
    # so it can't regress silently.
    parsed = chk.parse(chk_encode.build_chk([(b"STR ", b"hello")]))
    assert parsed.get("STR ") == b"hello"
    assert parsed.get("STR") is None


def test_resync_recovers_from_a_corrupted_declared_length() -> None:
    # Mirrors the real bug class this module exists to handle: a
    # section's declared length overshoots past where the next real
    # section actually starts (see docs/chk_trigger_format.md).
    real_mrgn = b"\x00" * 1280  # a plausible, correctly-sized MRGN payload
    good = chk_encode.build_chk([(b"MRGN", real_mrgn), (b"TRIG", b"\x00" * 2400)])

    # Corrupt MRGN's declared length in place: claim it's 100 bytes longer
    # than it really is, eating into TRIG's own header.
    import struct

    corrupted = bytearray(good)
    tag, length = struct.unpack_from("<4sI", corrupted, 0)
    assert tag == b"MRGN"
    struct.pack_into("<I", corrupted, 4, length + 100)

    parsed = chk.parse(bytes(corrupted))
    assert b"MRGN" in parsed.resynced
    # Despite the corrupted length, TRIG should still be found intact.
    assert parsed.get("TRIG") == b"\x00" * 2400
