#!/usr/bin/env python3
"""
Dump a human-readable trigger listing for a .scx/.scm StarCraft map.

Usage:
    python scripts/analyze_map.py "Elements RPG 2026.scx"
    python scripts/analyze_map.py "Elements RPG 2026.scx" --trigger 5
    python scripts/analyze_map.py "Elements RPG 2026.scx" --summary
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chktrig import chk, locations, mpq, strings, triggers


def load(map_path: Path):
    chk_bytes = mpq.extract_scenario_chk(map_path)
    chk_file = chk.parse(chk_bytes)
    str_table = strings.StringTable(chk_file)
    mrgn = chk_file.get("MRGN")
    locs = locations.decode_mrgn(mrgn) if mrgn else []
    ctx = triggers.DecodeContext(strings=str_table, locations=locs)
    trig_data = chk_file.get("TRIG") or b""
    trig_list = triggers.decode_trig(trig_data)
    return chk_file, ctx, trig_list


def print_trigger(i: int, trig, ctx) -> None:
    owned_by = [
        triggers.PLAYER_IDS[p] if p < len(triggers.PLAYER_IDS) else f"slot{p}"
        for p, on in enumerate(trig.owners)
        if on
    ]
    print(f"--- Trigger {i} --- owners: {', '.join(owned_by) or '(none)'}")
    for c in trig.conditions:
        print(f"  IF   {triggers.format_condition(c, ctx)}")
    for a in trig.actions:
        preserve = " [PRESERVE]" if a.type == 3 else ""
        print(f"  THEN {triggers.format_action(a, ctx)}{preserve}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("map_path", type=Path)
    ap.add_argument("--trigger", type=int, help="print only this trigger index (0-based)")
    ap.add_argument("--summary", action="store_true", help="print opcode frequency summary instead of full dump")
    ap.add_argument("--limit", type=int, default=None, help="print at most N triggers")
    args = ap.parse_args()

    chk_file, ctx, trig_list = load(args.map_path)

    print(f"Map: {args.map_path.name}")
    print(f"CHK sections present: {sorted(t.decode('ascii', 'replace').strip() for t in chk_file.sections)}")
    if chk_file.resynced:
        names = ", ".join(t.decode("ascii", "replace").strip() for t in chk_file.resynced)
        print(f"NOTE: had to resync past corrupted length field(s) for: {names}")
        print("      (common in 'protected' maps - see docs/chk_trigger_format.md)")
    print(f"Trigger count: {len(trig_list)}")
    print()

    if args.summary:
        cond_counter = Counter(c.type_name for t in trig_list for c in t.conditions)
        act_counter = Counter(a.type_name for t in trig_list for a in t.actions)
        print("Condition types used:")
        for name, count in cond_counter.most_common():
            print(f"  {count:5d}  {name}")
        print("\nAction types used:")
        for name, count in act_counter.most_common():
            print(f"  {count:5d}  {name}")
        return

    if args.trigger is not None:
        print_trigger(args.trigger, trig_list[args.trigger], ctx)
        return

    for i, trig in enumerate(trig_list):
        if args.limit is not None and i >= args.limit:
            print(f"... ({len(trig_list) - args.limit} more triggers not shown; use --limit to see more)")
            break
        print_trigger(i, trig, ctx)


if __name__ == "__main__":
    main()
