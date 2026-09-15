"""
Encode/decode round-trip tests for chktrig/triggers.py - the
condition/action/trigger struct layer, independent of the MPQ/CHK
container around it.
"""

from chktrig import triggers


def test_condition_field_roundtrip() -> None:
    cond = triggers.make_condition(
        type=3,  # Bring
        player=0, comparison=0, amount=1, unit=0, location=2,
    )
    assert cond.type == 3
    assert cond.player == 0
    assert cond.amount == 1
    assert cond.unit == 0
    assert cond.location == 2
    assert cond.type_name == "Bring"


def test_action_field_roundtrip() -> None:
    act = triggers.make_action(type=1)  # Victory
    assert act.type == 1
    assert act.type_name == "Victory"


def test_encode_decode_trigger_roundtrip() -> None:
    trig = triggers.make_trigger(
        conditions=[
            triggers.make_condition(type=3, player=0, comparison=0, amount=1, unit=0, location=2),
        ],
        actions=[
            triggers.make_action(type=13, amount=0, byte8=4),  # Set Switch -> Set
            triggers.make_action(type=3),  # Preserve Trigger
        ],
        owners=[1] + [0] * 27,
    )
    encoded = triggers.encode_trigger(trig)
    assert len(encoded) == triggers.TRIGGER_SIZE

    (decoded,) = triggers.decode_trig(encoded)
    assert len(decoded.conditions) == 1
    assert decoded.conditions[0].type == 3
    assert decoded.conditions[0].location == 2
    assert len(decoded.actions) == 2
    assert decoded.actions[0].type == 13
    assert decoded.actions[1].type == 3
    assert decoded.owners == [1] + [0] * 27


def test_encode_decode_multiple_triggers() -> None:
    trig_a = triggers.make_trigger(conditions=[triggers.make_condition(type=22)], actions=[])  # Always
    trig_b = triggers.make_trigger(conditions=[], actions=[triggers.make_action(type=1)])  # Victory

    data = triggers.encode_trig([trig_a, trig_b])
    assert len(data) == 2 * triggers.TRIGGER_SIZE

    decoded = triggers.decode_trig(data)
    assert len(decoded) == 2
    assert decoded[0].conditions[0].type_name == "Always"
    assert decoded[1].actions[0].type_name == "Victory"


def test_blank_trigger_is_all_no_condition_no_action() -> None:
    trig = triggers.make_trigger(conditions=[], actions=[])
    (decoded,) = triggers.decode_trig(triggers.encode_trigger(trig))
    assert decoded.conditions[0].type_name == "No Condition"
    assert decoded.actions[0].type_name == "No Action"


def test_location_raw_roundtrip() -> None:
    assert triggers.location_raw(0) == 1
    assert triggers.location_raw(1) == 2
    assert triggers.location_raw(63) == 64  # "Anywhere"


def test_format_condition_and_action_do_not_raise() -> None:
    cond = triggers.make_condition(type=3, player=0, comparison=0, amount=1, unit=0, location=2)
    act = triggers.make_action(type=1)
    # No DecodeContext - should fall back to raw numbers, not crash.
    assert "Bring" in triggers.format_condition(cond)
    assert "Victory" in triggers.format_action(act)
