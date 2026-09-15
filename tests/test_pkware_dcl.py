"""
Round-trip tests for the PKWARE DCL codec (chktrig/pkware_dcl.py).

This is the exact kind of test that caught real problems during
development - see .ai/context.md's "implode" entries. Kept here so a
regression (e.g. a change to the length/distance code tables, or to the
bit-packing order) fails loudly instead of silently producing a corrupt
map.
"""

import os

import pytest

from chktrig import pkware_dcl


def roundtrip(data: bytes) -> None:
    packed = pkware_dcl.implode(data)
    assert pkware_dcl.explode(packed) == data


def test_empty_via_explode_of_implode() -> None:
    # implode() always emits at least a 2-byte header + terminator, even
    # for empty input - explode() should get back exactly nothing.
    assert pkware_dcl.explode(pkware_dcl.implode(b"")) == b""


@pytest.mark.parametrize(
    "data",
    [
        b"a",
        b"hello world",
        b"a" * 1000,  # highly repetitive - should compress dramatically
        b"abcabcabcabcabcabc" * 50,  # short repeating pattern
        bytes(range(256)) * 20,  # every byte value, repeated
        b"\x00" * 5700 + b"\x03" * 1748,  # shape of real CHK filler data
    ],
    ids=["single-byte", "short-text", "long-run", "repeating-pattern", "all-byte-values", "chk-like-filler"],
)
def test_roundtrip_deterministic_inputs(data: bytes) -> None:
    roundtrip(data)


@pytest.mark.parametrize("size", [1, 2, 3, 4, 100, 500, 5000], ids=lambda n: f"{n}b")
def test_roundtrip_random_inputs(size: int) -> None:
    # Random data barely compresses (or inflates slightly) - the point
    # here is correctness of the literal-encoding path, not ratio.
    roundtrip(os.urandom(size))


def test_compresses_repetitive_data_smaller_than_input() -> None:
    # Not just correctness - implode should actually shrink real
    # CHK-shaped content, since mpq_write.py's per-sector encryption
    # padding relies on the compressed form usually being smaller.
    data = b"\x01" * 5700  # shape of a real PUNI section's availability fill
    packed = pkware_dcl.implode(data)
    assert len(packed) < len(data)
