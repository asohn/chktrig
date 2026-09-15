"""
Integration/regression test for scripts/generate_marine_map.py - the
proven, game-verified write-path generator.

This is the "master regression test" for the whole write path: it runs
the actual generator (not a re-implementation of it) and verifies the
output is a well-formed archive with everything the real map needs,
using this project's own read-path (chk.py / triggers.py) as the judge.

It deliberately never writes to the committed, known-working
maps_generated/marine_walk.scx - `main()` takes an explicit `out_path`
specifically so tests can redirect it to a throwaway path instead.
"""

import importlib.util
import sys
from pathlib import Path

from chktrig import chk, mpq, triggers

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_marine_map.py"

# scripts/ isn't a package, so import the module directly from its file path
# rather than fighting sys.path.
_spec = importlib.util.spec_from_file_location("generate_marine_map", SCRIPT_PATH)
generate_marine_map = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = generate_marine_map
_spec.loader.exec_module(generate_marine_map)

# Every section a real BroodWar-format (TYPE=RAWB) map needs, confirmed by
# exhaustive comparison against a real reference map (maps/marine_one.scx) -
# see docs/chk_trigger_format.md. TILE/ISOM are deliberately excluded: the
# game only reads MTXM at runtime.
EXPECTED_SECTIONS = {
    b"TYPE", b"VER ", b"IVE2", b"VCOD", b"IOWN", b"OWNR", b"ERA ", b"DIM ",
    b"SIDE", b"COLR", b"MTXM", b"DD2 ", b"THG2", b"MASK", b"FORC", b"SPRP",
    b"MRGN", b"TRIG", b"MBRF", b"PUNI", b"PUPx", b"UPGx", b"PTEx", b"TECx",
    b"UNIx", b"UNIT", b"WAV ", b"STR ", b"UPRP", b"UPUS", b"SWNM",
}


def test_generator_produces_a_well_formed_archive(tmp_path) -> None:
    out_path = tmp_path / "generated.scx"
    returned_bytes = generate_marine_map.main(out_path=out_path)

    # main() returns the same bytes it wrote to disk.
    assert out_path.read_bytes() == returned_bytes


def test_generated_archive_contains_all_required_chk_sections(tmp_path) -> None:
    out_path = tmp_path / "generated.scx"
    generate_marine_map.main(out_path=out_path)

    chk_bytes = mpq.extract_scenario_chk(str(out_path))
    parsed = chk.parse(chk_bytes)

    assert parsed.resynced == [], "generator's own output should never need resync"
    assert EXPECTED_SECTIONS <= set(parsed.sections), (
        f"missing sections: {EXPECTED_SECTIONS - set(parsed.sections)}"
    )


def test_generated_archive_has_two_triggers_with_the_expected_shape(tmp_path) -> None:
    # Mirrors the spec this whole map was built to satisfy: victory only
    # after BOTH the right-side arrival AND the return-to-origin have
    # fired (see docs/project_overview.md).
    out_path = tmp_path / "generated.scx"
    generate_marine_map.main(out_path=out_path)

    chk_bytes = mpq.extract_scenario_chk(str(out_path))
    parsed = chk.parse(chk_bytes)
    trig_bytes = parsed.get("TRIG")
    assert trig_bytes is not None

    decoded = triggers.decode_trig(trig_bytes)
    assert len(decoded) == 2

    all_conditions = [c for trig in decoded for c in trig.conditions]
    all_actions = [a for trig in decoded for a in trig.actions]

    condition_names = {c.type_name for c in all_conditions if c.type_name != "No Condition"}
    action_names = {a.type_name for a in all_actions if a.type_name != "No Action"}

    assert "Bring" in condition_names, "should check unit arrival at a location"
    assert "Victory" in action_names


def test_generated_archive_is_readable_by_a_second_independent_mpq_reader(tmp_path) -> None:
    # Confirms container-level correctness (header/hash table/block table)
    # independent of our own read path - mirrors
    # test_mpq_write.py::test_plain_mpyq_can_open_the_container.
    import mpyq

    out_path = tmp_path / "generated.scx"
    generate_marine_map.main(out_path=out_path)

    archive = mpyq.MPQArchive(str(out_path), listfile=False)
    try:
        assert archive.get_hash_table_entry(b"staredit\\scenario.chk") is not None
    finally:
        archive.file.close()


def test_generator_does_not_touch_the_committed_reference_map(tmp_path) -> None:
    # The whole point of the out_path parameter: running the generator in
    # tests must never overwrite the real, game-verified, tracked file.
    committed_path = generate_marine_map.OUT_PATH
    before = committed_path.read_bytes() if committed_path.exists() else None

    generate_marine_map.main(out_path=tmp_path / "generated.scx")

    after = committed_path.read_bytes() if committed_path.exists() else None
    assert before == after
